"""Incident role assignment persistence. Queries only; rules live in the role service."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.role_model import IncidentRoleAssignment


class IncidentRoleRepository:
    async def list_for_incident(
        self, session: AsyncSession, incident_id: uuid.UUID
    ) -> list[IncidentRoleAssignment]:
        assignments = await session.scalars(
            select(IncidentRoleAssignment)
            .where(IncidentRoleAssignment.incident_id == incident_id)
            .order_by(IncidentRoleAssignment.role)
        )
        return list(assignments)

    async def find(
        self, session: AsyncSession, incident_id: uuid.UUID, role: str
    ) -> IncidentRoleAssignment | None:
        assignment: IncidentRoleAssignment | None = await session.scalar(
            select(IncidentRoleAssignment).where(
                IncidentRoleAssignment.incident_id == incident_id,
                IncidentRoleAssignment.role == role,
            )
        )
        return assignment

    async def save(
        self, session: AsyncSession, assignment: IncidentRoleAssignment
    ) -> IncidentRoleAssignment:
        session.add(assignment)
        await session.flush()
        await session.refresh(assignment)
        return assignment

    async def remove(self, session: AsyncSession, assignment_id: uuid.UUID) -> None:
        await session.execute(
            delete(IncidentRoleAssignment).where(IncidentRoleAssignment.id == assignment_id)
        )
