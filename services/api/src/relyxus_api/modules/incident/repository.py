"""Incident persistence. Queries only; lifecycle and access rules live in the service.

Every read applies the incident visibility rule (`visibility.visible_to`) for the viewer
on the session, so restricted incidents are invisible rather than forbidden."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.viewer import get_viewer
from relyxus_api.modules.incident.affected_service_model import IncidentAffectedService
from relyxus_api.modules.incident.model import Incident
from relyxus_api.modules.incident.visibility import visible_to

_NUMBER_LOCK = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")


@dataclass(frozen=True, slots=True)
class IncidentListQuery:
    """Empty collections mean "any"."""

    lifecycle_states: Collection[str] = ()
    severities: Collection[str] = ()
    service_ids: Collection[uuid.UUID] = ()


class IncidentRepository:
    async def allocate_number(self, session: AsyncSession, workspace_id: uuid.UUID) -> int:
        """Next per-workspace number. The transaction-scoped lock serialises concurrent
        creations in one workspace; the unique constraint is the backstop."""
        await session.execute(_NUMBER_LOCK, {"key": f"incident-number:{workspace_id}"})
        highest = await session.scalar(
            select(func.max(Incident.number)).where(Incident.workspace_id == workspace_id)
        )
        return (highest or 0) + 1

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
                Incident.id == incident_id,
                Incident.workspace_id == workspace_id,
                visible_to(get_viewer(session)),
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
            .where(
                Incident.id == incident_id,
                Incident.workspace_id == workspace_id,
                visible_to(get_viewer(session)),
            )
            .with_for_update(of=Incident)
        )
        return incident

    async def save(self, session: AsyncSession, incident: Incident) -> Incident:
        await session.flush()
        await session.refresh(incident)
        return incident

    async def list_in_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        filters: IncidentListQuery,
        before_id: uuid.UUID | None,
        limit: int,
    ) -> list[Incident]:
        """Newest first (UUIDv7 IDs sort by creation time); keyset page before `before_id`."""
        query = select(Incident).where(
            Incident.workspace_id == workspace_id, visible_to(get_viewer(session))
        )
        if filters.lifecycle_states:
            query = query.where(Incident.lifecycle_state.in_(filters.lifecycle_states))
        if filters.severities:
            query = query.where(Incident.severity.in_(filters.severities))
        if filters.service_ids:
            query = query.where(
                select(IncidentAffectedService.id)
                .where(
                    IncidentAffectedService.incident_id == Incident.id,
                    IncidentAffectedService.service_id.in_(filters.service_ids),
                )
                .exists()
            )
        if before_id is not None:
            query = query.where(Incident.id < before_id)
        incidents = await session.scalars(query.order_by(Incident.id.desc()).limit(limit))
        return list(incidents)
