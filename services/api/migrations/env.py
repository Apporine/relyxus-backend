"""Alembic environment: async, URL from RELYXUS_DATABASE_URL or the caller's config."""

import asyncio
import os
import sys

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from relyxus_api.shared.db.base import Base

DATABASE_URL_VARIABLE = "RELYXUS_DATABASE_URL"
URL_ATTRIBUTE = "database_url"


def _database_url() -> str:
    configured = context.config.attributes.get(URL_ATTRIBUTE) or os.environ.get(
        DATABASE_URL_VARIABLE
    )
    if not configured:
        raise RuntimeError(f"Set {DATABASE_URL_VARIABLE} to run migrations")
    return str(configured)


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(_database_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline SQL generation is not supported; run against a database")
# psycopg's async driver cannot use Windows' default Proactor loop (local development only).
asyncio.run(
    _run_online(), loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None
)
