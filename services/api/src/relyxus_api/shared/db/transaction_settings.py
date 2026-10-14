"""Transaction-local PostgreSQL settings that row-level security policies read.

`set_config(..., is_local => true)` lasts only until the transaction ends, so a value can
never leak to another request that reuses the pooled connection.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_SET_LOCAL = text("SELECT set_config(:name, :value, true)")


async def set_transaction_settings(session: AsyncSession, settings: dict[str, str]) -> None:
    if not session.in_transaction():
        raise RuntimeError("Security context must be applied inside a transaction")
    for name, value in settings.items():
        await session.execute(_SET_LOCAL, {"name": name, "value": value})
