"""API database sessions run in UTC whatever the server default (ADR-0003)."""

import asyncio

import pytest
from sqlalchemy import text

from api_test_support import make_settings
from db_test_support import require_test_database_url
from relyxus_api.shared.db.engine import create_database_engine

pytestmark = pytest.mark.integration


def test_sessions_use_utc() -> None:
    engine = create_database_engine(make_settings(database_url=require_test_database_url()))

    async def time_zone() -> str:
        try:
            async with engine.connect() as connection:
                return str(await connection.scalar(text("SHOW TimeZone")))
        finally:
            await engine.dispose()

    assert asyncio.run(time_zone()) == "UTC"
