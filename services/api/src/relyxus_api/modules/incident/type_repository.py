"""Incident type persistence. Queries only; rules live in the type service."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.type_model import IncidentType


class IncidentTypeRepository:
    async def save(self, session: AsyncSession, incident_type: IncidentType) -> IncidentType:
        session.add(incident_type)
        await session.flush()
        await session.refresh(incident_type)
        return incident_type

    async def find_by_key(
        self, session: AsyncSession, workspace_id: uuid.UUID, key: str
    ) -> IncidentType | None:
        found: IncidentType | None = await session.scalar(
            select(IncidentType).where(
                IncidentType.workspace_id == workspace_id, IncidentType.key == key
            )
        )
        return found

    async def find_in_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        type_id: uuid.UUID,
        *,
        is_locking: bool = False,
    ) -> IncidentType | None:
        query = select(IncidentType).where(
            IncidentType.id == type_id, IncidentType.workspace_id == workspace_id
        )
        if is_locking:
            query = query.with_for_update()
        found: IncidentType | None = await session.scalar(query)
        return found

    async def list_in_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        include_archived: bool,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[IncidentType]:
        """Oldest first (UUIDv7 order), keyset page after `after_id`."""
        query = select(IncidentType).where(IncidentType.workspace_id == workspace_id)
        if not include_archived:
            query = query.where(IncidentType.archived_at.is_(None))
        if after_id is not None:
            query = query.where(IncidentType.id > after_id)
        types = await session.scalars(query.order_by(IncidentType.id).limit(limit))
        return list(types)
