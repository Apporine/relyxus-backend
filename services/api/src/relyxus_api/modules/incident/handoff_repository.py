"""Incident role handoff persistence. Queries only; rules live in the handoff service."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.handoff_model import HandoffState, IncidentRoleHandoff


class IncidentHandoffRepository:
    async def save(
        self, session: AsyncSession, handoff: IncidentRoleHandoff
    ) -> IncidentRoleHandoff:
        session.add(handoff)
        await session.flush()
        await session.refresh(handoff)
        return handoff

    async def find_pending(
        self, session: AsyncSession, incident_id: uuid.UUID, role: str
    ) -> IncidentRoleHandoff | None:
        handoff: IncidentRoleHandoff | None = await session.scalar(
            select(IncidentRoleHandoff).where(
                IncidentRoleHandoff.incident_id == incident_id,
                IncidentRoleHandoff.role == role,
                IncidentRoleHandoff.state == HandoffState.PENDING.value,
            )
        )
        return handoff

    async def lock(
        self, session: AsyncSession, incident_id: uuid.UUID, handoff_id: uuid.UUID
    ) -> IncidentRoleHandoff | None:
        handoff: IncidentRoleHandoff | None = await session.scalar(
            select(IncidentRoleHandoff)
            .where(
                IncidentRoleHandoff.id == handoff_id,
                IncidentRoleHandoff.incident_id == incident_id,
            )
            .with_for_update()
        )
        return handoff

    async def list_for_incident(
        self,
        session: AsyncSession,
        incident_id: uuid.UUID,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[IncidentRoleHandoff]:
        """Oldest first (UUIDv7 order), keyset page after `after_id`."""
        query = select(IncidentRoleHandoff).where(IncidentRoleHandoff.incident_id == incident_id)
        if after_id is not None:
            query = query.where(IncidentRoleHandoff.id > after_id)
        handoffs = await session.scalars(query.order_by(IncidentRoleHandoff.id).limit(limit))
        return list(handoffs)
