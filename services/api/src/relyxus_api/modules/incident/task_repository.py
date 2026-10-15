"""Incident task persistence. Queries only; rules live in the task service."""

import uuid
from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.task_model import IncidentTask


class IncidentTaskRepository:
    async def save(self, session: AsyncSession, task: IncidentTask) -> IncidentTask:
        session.add(task)
        await session.flush()
        await session.refresh(task)
        return task

    async def lock(
        self, session: AsyncSession, incident_id: uuid.UUID, task_id: uuid.UUID
    ) -> IncidentTask | None:
        task: IncidentTask | None = await session.scalar(
            select(IncidentTask)
            .where(IncidentTask.id == task_id, IncidentTask.incident_id == incident_id)
            .with_for_update()
        )
        return task

    async def list_for_incident(
        self,
        session: AsyncSession,
        incident_id: uuid.UUID,
        after_id: uuid.UUID | None,
        limit: int,
        statuses: Collection[str] = (),
    ) -> list[IncidentTask]:
        """Oldest first (UUIDv7 order), keyset page after `after_id`; empty statuses = any."""
        query = select(IncidentTask).where(IncidentTask.incident_id == incident_id)
        if statuses:
            query = query.where(IncidentTask.status.in_(statuses))
        if after_id is not None:
            query = query.where(IncidentTask.id > after_id)
        tasks = await session.scalars(query.order_by(IncidentTask.id).limit(limit))
        return list(tasks)

    async def list_unfinished_for_incident(
        self, session: AsyncSession, incident_id: uuid.UUID, statuses: list[str], limit: int
    ) -> list[IncidentTask]:
        """Tasks in the given statuses, soonest due first (undated last), then oldest."""
        tasks = await session.scalars(
            select(IncidentTask)
            .where(IncidentTask.incident_id == incident_id, IncidentTask.status.in_(statuses))
            .order_by(IncidentTask.due_at.asc().nulls_last(), IncidentTask.id)
            .limit(limit)
        )
        return list(tasks)
