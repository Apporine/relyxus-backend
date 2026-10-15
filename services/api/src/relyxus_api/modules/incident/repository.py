"""Incident persistence. Queries only; lifecycle and access rules live in the service."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.model import Incident


class IncidentRepository:
    async def add(self, session: AsyncSession, incident: Incident) -> Incident:
        session.add(incident)
        await session.flush()
        await session.refresh(incident)
        return incident

    async def find_in_workspace(
        self, session: AsyncSession, workspace_id: uuid.UUID, incident_id: uuid.UUID
    ) -> Incident | None:
        # RLS scopes by organisation; the workspace filter keeps sibling workspaces of the
        # same organisation out.
        incident: Incident | None = await session.scalar(
            select(Incident).where(
                Incident.id == incident_id, Incident.workspace_id == workspace_id
            )
        )
        return incident
