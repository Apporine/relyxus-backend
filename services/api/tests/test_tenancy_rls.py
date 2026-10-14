"""Tenant isolation through PostgreSQL row-level security (MP-10.01, MP-33.01 RLS tests).

Every check runs as a dedicated non-superuser role, because superusers bypass RLS and a test
run as one would prove nothing.
"""

import asyncio
import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import relyxus_api.models  # noqa: F401  (registers every table on Base.metadata)
from api_test_support import make_settings
from db_test_support import (
    PROBE_ROLE,
    SessionWork,
    migrate_and_reset,
    require_test_database_url,
    run_as_probe_role,
    run_as_superuser,
)
from relyxus_api.app import create_app
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.modules.tenancy.model import Organization, Workspace
from relyxus_api.shared.config.settings import Environment
from relyxus_api.shared.db.base import Base
from relyxus_api.shared.db.engine import create_session_factory, is_row_level_security_enforced

pytestmark = pytest.mark.integration
ORG_A, ORG_B = uuid.uuid4(), uuid.uuid4()
WORKSPACE_A, WORKSPACE_B = uuid.uuid4(), uuid.uuid4()


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)
    run_as_superuser(url, _seed_two_tenants)
    return url


async def _seed_two_tenants(session: AsyncSession) -> None:
    for organization_id, workspace_id, key in (
        (ORG_A, WORKSPACE_A, "alpha"),
        (ORG_B, WORKSPACE_B, "bravo"),
    ):
        session.add(
            Organization(
                id=organization_id, name=key, deployment_mode="saas", default_region="eu-west-2"
            )
        )
        await session.flush()
        session.add(
            Workspace(
                id=workspace_id,
                organization_id=organization_id,
                key=key,
                name=key,
                data_residency_region="eu-west-2",
            )
        )


def _run_as_tenant[ResultT](
    url: str, context: TenantContext | None, work: SessionWork[ResultT]
) -> ResultT:
    async def with_context(session: AsyncSession) -> ResultT:
        if context is not None:
            await apply_tenant_context(session, context)
        return await work(session)

    return run_as_probe_role(url, with_context)


async def _visible_workspace_ids(session: AsyncSession) -> set[uuid.UUID]:
    return set((await session.scalars(select(Workspace.id))).all())


async def _visible_organization_ids(session: AsyncSession) -> set[uuid.UUID]:
    return set((await session.scalars(select(Organization.id))).all())


def test_rls_is_enabled_and_forced_on_tenant_tables(database_url: str) -> None:
    async def read_flags() -> dict[str, tuple[bool, bool]]:
        engine = create_async_engine(database_url)
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class"
                    " WHERE relname IN ('organizations', 'workspaces')"
                )
            )
            flags = {row[0]: (row[1], row[2]) for row in rows}
        await engine.dispose()
        return flags

    assert asyncio.run(read_flags()) == {"organizations": (True, True), "workspaces": (True, True)}


def test_tenant_sees_only_its_own_rows(database_url: str) -> None:
    context = TenantContext(organization_id=ORG_A)

    assert _run_as_tenant(database_url, context, _visible_organization_ids) == {ORG_A}
    assert _run_as_tenant(database_url, context, _visible_workspace_ids) == {WORKSPACE_A}


def test_missing_context_sees_nothing(database_url: str) -> None:
    assert _run_as_tenant(database_url, None, _visible_organization_ids) == set()
    assert _run_as_tenant(database_url, None, _visible_workspace_ids) == set()


def test_tenant_cannot_create_rows_in_another_tenant(database_url: str) -> None:
    async def insert_foreign_workspace(session: AsyncSession) -> None:
        session.add(
            Workspace(
                organization_id=ORG_B, key="intruder", name="x", data_residency_region="eu-west-2"
            )
        )
        await session.flush()

    with pytest.raises(DBAPIError, match="row-level security"):
        _run_as_tenant(database_url, TenantContext(organization_id=ORG_A), insert_foreign_workspace)


def test_tenant_cannot_move_its_rows_to_another_tenant(database_url: str) -> None:
    async def move_workspace(session: AsyncSession) -> None:
        await session.execute(
            text("UPDATE workspaces SET organization_id = :target WHERE id = :id"),
            {"target": ORG_B, "id": WORKSPACE_A},
        )

    with pytest.raises(DBAPIError, match="row-level security"):
        _run_as_tenant(database_url, TenantContext(organization_id=ORG_A), move_workspace)


def test_context_does_not_outlive_its_transaction(database_url: str) -> None:
    async def two_transactions() -> tuple[set[uuid.UUID], set[uuid.UUID]]:
        engine = create_async_engine(database_url, pool_size=1, max_overflow=0)
        sessions = create_session_factory(engine)
        async with sessions() as session, session.begin():
            await session.execute(text(f"SET LOCAL ROLE {PROBE_ROLE}"))
            await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
            first = await _visible_workspace_ids(session)
        async with sessions() as session, session.begin():
            await session.execute(text(f"SET LOCAL ROLE {PROBE_ROLE}"))
            second = await _visible_workspace_ids(session)
        await engine.dispose()
        return first, second

    assert asyncio.run(two_transactions()) == ({WORKSPACE_A}, set())


def test_apply_tenant_context_requires_a_transaction(database_url: str) -> None:
    async def outside_transaction() -> None:
        engine = create_async_engine(database_url)
        async with create_session_factory(engine)() as session:
            await apply_tenant_context(session, TenantContext(organization_id=ORG_A))

    with pytest.raises(RuntimeError, match="inside a transaction"):
        asyncio.run(outside_transaction())


def test_models_match_migrations(database_url: str) -> None:
    async def diff() -> list[object]:
        engine = create_async_engine(database_url)
        async with engine.connect() as connection:
            differences = await connection.run_sync(
                lambda sync: compare_metadata(MigrationContext.configure(sync), Base.metadata)
            )
        await engine.dispose()
        return list(differences)

    assert asyncio.run(diff()) == []


def test_superuser_connection_is_reported_unsafe_outside_local(database_url: str) -> None:
    async def role_check() -> bool:
        engine = create_async_engine(database_url)
        try:
            return await is_row_level_security_enforced(engine, 2.0)
        finally:
            await engine.dispose()

    if asyncio.run(role_check()):
        pytest.skip("test database role is not a superuser; nothing to demonstrate")
    with TestClient(create_app(make_settings(Environment.STAGING, database_url))) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert {"name": "postgresql_row_level_security", "is_reachable": False} in response.json()[
        "data"
    ]["checks"]
