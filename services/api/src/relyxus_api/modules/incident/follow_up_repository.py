"""Follow-up persistence. Queries only; rules live in the follow-up service."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.follow_up_model import IncidentFollowUp


class IncidentFollowUpRepository:
    async def save(self, session: AsyncSession, follow_up: IncidentFollowUp) -> IncidentFollowUp:
        session.add(follow_up)
        await session.flush()
        await session.refresh(follow_up)
        return follow_up

    async def lock(
        self, session: AsyncSession, incident_id: uuid.UUID, follow_up_id: uuid.UUID
    ) -> IncidentFollowUp | None:
        follow_up: IncidentFollowUp | None = await session.scalar(
            select(IncidentFollowUp)
            .where(IncidentFollowUp.id == follow_up_id, IncidentFollowUp.incident_id == incident_id)
            .with_for_update()
        )
        return follow_up

    async def list_for_incident(
        self,
        session: AsyncSession,
        incident_id: uuid.UUID,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[IncidentFollowUp]:
        """Oldest first (UUIDv7 order), keyset page after `after_id`."""
        query = select(IncidentFollowUp).where(IncidentFollowUp.incident_id == incident_id)
        if after_id is not None:
            query = query.where(IncidentFollowUp.id > after_id)
        follow_ups = await session.scalars(query.order_by(IncidentFollowUp.id).limit(limit))
        return list(follow_ups)
