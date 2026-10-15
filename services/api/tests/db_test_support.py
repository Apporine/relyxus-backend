"""Shared helpers for integration tests that need a real PostgreSQL (context.md §13).

RLS assertions run as `PROBE_ROLE`, a non-superuser role without BYPASSRLS: a superuser
skips every policy, so a test run as one would prove nothing.
"""

import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from api_test_support import get_test_database_url
from relyxus_api.shared.db.engine import create_session_factory

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
PROBE_ROLE = "relyxus_rls_probe"
# Child tables first so deletes respect foreign keys.
TENANT_TABLES = (
    "incident_tasks",
    "incident_role_assignments",
    "incidents",
    "audit_events",
    "workspace_memberships",
    "users",
    "workspaces",
    "organizations",
)

_CREATE_PROBE_ROLE = (
    f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{PROBE_ROLE}') "
    f"THEN CREATE ROLE {PROBE_ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF; END $$"
)

type SessionWork[ResultT] = Callable[[AsyncSession], Awaitable[ResultT]]


def require_test_database_url() -> str:
    """The test database URL, or skip; CI sets RELYXUS_REQUIRE_INTEGRATION=1 to fail instead."""
    url = get_test_database_url()
    if url is None:
        if os.environ.get("RELYXUS_REQUIRE_INTEGRATION") == "1":
            pytest.fail("RELYXUS_TEST_DATABASE_URL is required in this environment")
        pytest.skip("RELYXUS_TEST_DATABASE_URL not set")
    return url


def build_alembic_config(url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = url
    return config


def migrate_and_reset(url: str) -> None:
    """Upgrade to head, ensure the probe role and grants exist, and empty tenant tables."""
    command.upgrade(build_alembic_config(url), "head")

    async def reset() -> None:
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            await connection.execute(text(_CREATE_PROBE_ROLE))
            tables = ", ".join(TENANT_TABLES)
            await connection.execute(
                text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tables} TO {PROBE_ROLE}")
            )
            # TRUNCATE avoids firing row DELETE triggers (audit_events is append-only).
            await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        await engine.dispose()

    asyncio.run(reset())


def run_as_superuser[ResultT](url: str, work: SessionWork[ResultT]) -> ResultT:
    """Seed or inspect data with RLS bypassed (the test database owner)."""

    async def run() -> ResultT:
        engine = create_async_engine(url)
        try:
            async with create_session_factory(engine)() as session, session.begin():
                return await work(session)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def run_as_probe_role[ResultT](url: str, work: SessionWork[ResultT]) -> ResultT:
    """Run `work` in one transaction as the non-superuser probe role, so RLS applies."""

    async def as_probe(session: AsyncSession) -> ResultT:
        await session.execute(text(f"SET LOCAL ROLE {PROBE_ROLE}"))
        return await work(session)

    return run_as_superuser(url, as_probe)
