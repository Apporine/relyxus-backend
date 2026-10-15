"""Incident access grant persistence. Queries only; rules live in the visibility service."""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.access_grant_model import MAX_ACCESS_GRANTS, IncidentAccessGrant


class AccessGrantRepository:
    async def add(self, session: AsyncSession, grant: IncidentAccessGrant) -> IncidentAccessGrant:
        session.add(grant)
        await session.flush()
        await session.refresh(grant)
        return grant

    async def find(
        self, session: AsyncSession, incident_id: uuid.UUID, grant_id: uuid.UUID
    ) -> IncidentAccessGrant | None:
        grant: IncidentAccessGrant | None = await session.scalar(
            select(IncidentAccessGrant).where(
                IncidentAccessGrant.id == grant_id, IncidentAccessGrant.incident_id == incident_id
            )
        )
        return grant

    async def find_person_grant(
        self, session: AsyncSession, incident_id: uuid.UUID, user_id: uuid.UUID
    ) -> IncidentAccessGrant | None:
        """A non-expiring person grant for this user, if any."""
        grant: IncidentAccessGrant | None = await session.scalar(
            select(IncidentAccessGrant)
            .where(
                IncidentAccessGrant.incident_id == incident_id,
                IncidentAccessGrant.user_id == user_id,
                IncidentAccessGrant.expires_at.is_(None),
            )
            .limit(1)
        )
        return grant

    async def count_for_incident(self, session: AsyncSession, incident_id: uuid.UUID) -> int:
        count = await session.scalar(
            select(func.count()).where(IncidentAccessGrant.incident_id == incident_id)
        )
        return int(count or 0)

    async def list_for_incident(
        self, session: AsyncSession, incident_id: uuid.UUID
    ) -> list[IncidentAccessGrant]:
        """Oldest first; bounded by MAX_ACCESS_GRANTS, enforced when granting."""
        grants = await session.scalars(
            select(IncidentAccessGrant)
            .where(IncidentAccessGrant.incident_id == incident_id)
            .order_by(IncidentAccessGrant.id)
            .limit(MAX_ACCESS_GRANTS)
        )
        return list(grants)

    async def remove(self, session: AsyncSession, grant_id: uuid.UUID) -> None:
        await session.execute(delete(IncidentAccessGrant).where(IncidentAccessGrant.id == grant_id))
