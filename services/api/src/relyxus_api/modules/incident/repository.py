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

    async def lock_in_workspace(
        self, session: AsyncSession, workspace_id: uuid.UUID, incident_id: uuid.UUID
    ) -> Incident | None:
        """Row-locks the incident for the rest of the transaction, so concurrent
        transitions on the same incident run one after another."""
        incident: Incident | None = await session.scalar(
            select(Incident)
            .where(Incident.id == incident_id, Incident.workspace_id == workspace_id)
            .with_for_update()
        )
        return incident

    async def save(self, session: AsyncSession, incident: Incident) -> Incident:
        await session.flush()
        await session.refresh(incident)
        return incident
