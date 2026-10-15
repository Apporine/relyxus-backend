"""Incident timeline persistence. Append and read only; rows are immutable."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.timeline_model import IncidentTimelineEvent


class IncidentTimelineRepository:
    async def append(
        self, session: AsyncSession, event: IncidentTimelineEvent
    ) -> IncidentTimelineEvent:
        session.add(event)
        await session.flush()
        await session.refresh(event)
        return event

    async def list_for_incident(
        self,
        session: AsyncSession,
        incident_id: uuid.UUID,
        after_sequence: int | None,
        limit: int,
    ) -> list[IncidentTimelineEvent]:
        """Oldest first, keyset page after `after_sequence`."""
        query = select(IncidentTimelineEvent).where(
            IncidentTimelineEvent.incident_id == incident_id
        )
        if after_sequence is not None:
            query = query.where(IncidentTimelineEvent.sequence > after_sequence)
        events = await session.scalars(query.order_by(IncidentTimelineEvent.sequence).limit(limit))
        return list(events)
