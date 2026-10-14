"""Integration tests against a real PostgreSQL (context.md §13).

Run with RELYXUS_TEST_DATABASE_URL set. CI sets RELYXUS_REQUIRE_INTEGRATION=1 so a missing
database fails the build instead of silently skipping these tests.
"""

import asyncio
import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import String, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from api_test_support import get_test_database_url, make_settings
from relyxus_api.app import create_app
from relyxus_api.shared.db.base import NAMING_CONVENTION, Base, RecordColumns
from relyxus_api.shared.db.engine import create_session_factory

pytestmark = pytest.mark.integration
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture(scope="module")
def database_url() -> str:
    url = get_test_database_url()
    if url is None:
        if os.environ.get("RELYXUS_REQUIRE_INTEGRATION") == "1":
            pytest.fail("RELYXUS_TEST_DATABASE_URL is required in this environment")
        pytest.skip("RELYXUS_TEST_DATABASE_URL not set")
    return url


class _ProbeBase(DeclarativeBase):
    metadata = Base.metadata.__class__(naming_convention=NAMING_CONVENTION)
    type_annotation_map = Base.type_annotation_map


class _ProbeRecord(RecordColumns, _ProbeBase):
    __tablename__ = "record_columns_probe"

    label: Mapped[str] = mapped_column(String(50))


def test_readiness_is_200_when_the_database_is_reachable(database_url: str) -> None:
    with TestClient(create_app(make_settings(database_url=database_url))) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["data"]["checks"] == [{"name": "postgresql", "is_reachable": True}]


def test_migrations_upgrade_to_head(database_url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = database_url

    command.upgrade(config, "head")
    command.upgrade(config, "head")

    async def read_version() -> str | None:
        engine = create_async_engine(database_url)
        async with engine.connect() as connection:
            version: str | None = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
        await engine.dispose()
        return version

    assert asyncio.run(read_version()) == "0001"


async def add_then_abort(sessions: async_sessionmaker[AsyncSession], record_id: uuid.UUID) -> None:
    async with sessions() as session, session.begin():
        session.add(_ProbeRecord(id=record_id, label="discarded"))
        await session.flush()
        raise RuntimeError("abort the unit of work")


def test_record_columns_and_transactions(database_url: str) -> None:
    async def exercise() -> None:
        engine = create_async_engine(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(_ProbeBase.metadata.drop_all)
            await connection.run_sync(_ProbeBase.metadata.create_all)
        sessions = create_session_factory(engine)

        async with sessions() as session, session.begin():
            record = _ProbeRecord(label="first")
            session.add(record)
        assert record.id.version == 7

        async with sessions() as session:
            stored = await session.get(_ProbeRecord, record.id)
        assert stored is not None
        assert stored.created_at.tzinfo is not None
        assert stored.updated_at == stored.created_at

        async with sessions() as session, session.begin():
            to_rename = await session.get(_ProbeRecord, record.id)
            assert to_rename is not None
            to_rename.label = "renamed"

        async with sessions() as session:
            renamed = await session.get(_ProbeRecord, record.id)
        assert renamed is not None
        assert renamed.label == "renamed"
        assert renamed.updated_at > stored.created_at

        rolled_back_id = uuid.uuid4()
        with pytest.raises(RuntimeError):
            await add_then_abort(sessions, rolled_back_id)
        async with sessions() as session:
            found = await session.scalar(
                select(_ProbeRecord).where(_ProbeRecord.id == rolled_back_id)
            )
        assert found is None

        async with engine.begin() as connection:
            await connection.run_sync(_ProbeBase.metadata.drop_all)
        await engine.dispose()

    asyncio.run(exercise())
