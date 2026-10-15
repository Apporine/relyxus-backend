"""Database engine, sessions and the readiness probe (MP-25.01: explicit transactions).

Repositories receive an `AsyncSession`; services own the transaction boundary with
`async with session.begin():` so every multi-write operation commits or rolls back as one
unit (context.md §9).
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from relyxus_api.shared.config.settings import Settings

logger = logging.getLogger(__name__)


def create_database_engine(settings: Settings) -> AsyncEngine:
    """Lazy: no connection is opened until first use, so startup never blocks on the DB."""
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        hide_parameters=True,
    )
    event.listen(engine.sync_engine, "connect", _use_utc)
    return engine


def _use_utc(dbapi_connection: Any, _connection_record: Any) -> None:
    """Timestamps leave the database in UTC whatever the server's default time zone
    (ADR-0003: API timestamps are UTC). PgBouncer tracks TimeZone per client."""
    cursor = dbapi_connection.cursor()
    cursor.execute("SET TIME ZONE 'UTC'")
    cursor.close()


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def is_database_reachable(engine: AsyncEngine, timeout_seconds: float) -> bool:
    try:
        async with asyncio.timeout(timeout_seconds), engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError):
        logger.warning("database readiness check failed", exc_info=True)
        return False
    return True


_ROLE_RESPECTS_RLS = text(
    "SELECT NOT (rolsuper OR rolbypassrls) FROM pg_roles WHERE rolname = current_user"
)


async def is_row_level_security_enforced(engine: AsyncEngine, timeout_seconds: float) -> bool:
    """False when the application's database role would silently bypass every RLS policy
    (superuser or BYPASSRLS). Tenant isolation must never depend on such a role."""
    try:
        async with asyncio.timeout(timeout_seconds), engine.connect() as connection:
            return bool(await connection.scalar(_ROLE_RESPECTS_RLS))
    except (SQLAlchemyError, OSError, TimeoutError):
        logger.warning("row-level security role check failed", exc_info=True)
        return False


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


DatabaseSessionDependency = Annotated[AsyncSession, Depends(get_database_session)]
