"""Per-chain advisory locks so concurrent appends get distinct sequences (Q-19)."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_MASK_64 = (1 << 64) - 1
_SIGNED_64 = 1 << 63


def _as_signed_int64(value: int) -> int:
    masked = value & _MASK_64
    return masked - (1 << 64) if masked >= _SIGNED_64 else masked


def advisory_lock_key(chain_id: uuid.UUID) -> int:
    """Fold the UUID into one signed int64 for ``pg_advisory_xact_lock(bigint)``."""
    value = chain_id.int
    return _as_signed_int64(value ^ (value >> 64))


async def lock_chain_for_append(session: AsyncSession, chain_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": advisory_lock_key(chain_id)}
    )
