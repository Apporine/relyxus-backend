"""Database CHECK constraint names match the models (migration 0034).

Guards against naming a constraint "ck_<table>_<name>" in a migration without `op.f()`,
which makes the naming convention apply twice ("ck_<table>_ck_<table>_<name>").
"""

import pytest
from sqlalchemy import CheckConstraint, text
from sqlalchemy.ext.asyncio import AsyncSession

import relyxus_api.models  # noqa: F401  (registers every table on Base.metadata)
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.shared.db.base import Base

pytestmark = pytest.mark.integration


def test_check_constraint_names_match_the_models() -> None:
    url = require_test_database_url()
    migrate_and_reset(url)
    declared = {
        (table.name, str(constraint.name))
        for table in Base.metadata.sorted_tables
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    async def in_database(session: AsyncSession) -> set[tuple[str, str]]:
        rows = await session.execute(
            text(
                "SELECT conrelid::regclass::text, conname FROM pg_constraint"
                " WHERE contype = 'c' AND connamespace = 'public'::regnamespace"
            )
        )
        return {(str(table), str(name)) for table, name in rows}

    actual = run_as_superuser(url, in_database)

    assert actual == declared
