"""Affected-service persistence. Queries only; rules live in the services."""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.affected_service_model import (
    MAX_AFFECTED_SERVICES,
    IncidentAffectedService,
)


class AffectedServiceRepository:
    async def add(
        self, session: AsyncSession, link: IncidentAffectedService
    ) -> IncidentAffectedService:
        session.add(link)
        await session.flush()
        await session.refresh(link)
        return link

    async def find(
        self, session: AsyncSession, incident_id: uuid.UUID, service_id: uuid.UUID
    ) -> IncidentAffectedService | None:
        link: IncidentAffectedService | None = await session.scalar(
            select(IncidentAffectedService).where(
                IncidentAffectedService.incident_id == incident_id,
                IncidentAffectedService.service_id == service_id,
            )
        )
        return link

    async def count_for_incident(self, session: AsyncSession, incident_id: uuid.UUID) -> int:
        count = await session.scalar(
            select(func.count()).where(IncidentAffectedService.incident_id == incident_id)
        )
        return int(count or 0)

    async def list_for_incident(
        self, session: AsyncSession, incident_id: uuid.UUID
    ) -> list[IncidentAffectedService]:
        """Bounded by MAX_AFFECTED_SERVICES, enforced when linking."""
        links = await session.scalars(
            select(IncidentAffectedService)
            .where(IncidentAffectedService.incident_id == incident_id)
            .order_by(IncidentAffectedService.id)
            .limit(MAX_AFFECTED_SERVICES)
        )
        return list(links)

    async def remove(self, session: AsyncSession, link_id: uuid.UUID) -> None:
        await session.execute(
            delete(IncidentAffectedService).where(IncidentAffectedService.id == link_id)
        )
