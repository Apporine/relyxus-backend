"""Audit chain persistence. Append-only rules are enforced in the database (migration 0005)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.audit.chain_lock import lock_chain_for_append
from relyxus_api.modules.audit.model import AuditEvent


@dataclass(frozen=True, slots=True)
class ChainTail:
    sequence: int
    entry_hash: str


class AuditRepository:
    async def lock_chain(self, session: AsyncSession, chain_id: uuid.UUID) -> None:
        await lock_chain_for_append(session, chain_id)

    async def fetch_chain_tail(
        self, session: AsyncSession, chain_id: uuid.UUID
    ) -> ChainTail | None:
        row = await session.execute(
            select(AuditEvent.sequence, AuditEvent.entry_hash)
            .where(AuditEvent.chain_id == chain_id)
            .order_by(AuditEvent.sequence.desc())
            .limit(1)
        )
        tail = row.first()
        return None if tail is None else ChainTail(sequence=tail[0], entry_hash=tail[1])

    async def list_chain_events(
        self, session: AsyncSession, chain_id: uuid.UUID
    ) -> list[AuditEvent]:
        events = await session.scalars(
            select(AuditEvent)
            .where(AuditEvent.chain_id == chain_id)
            .order_by(AuditEvent.sequence.asc())
        )
        return list(events)

    async def count_chain_events(self, session: AsyncSession, chain_id: uuid.UUID) -> int:
        count = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.chain_id == chain_id)
        )
        return int(count or 0)

    async def add_event(self, session: AsyncSession, event: AuditEvent) -> AuditEvent:
        session.add(event)
        await session.flush()
        return event
