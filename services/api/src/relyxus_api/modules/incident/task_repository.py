"""Incident task persistence. Queries only; rules live in the task service."""

import uuid

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
    ) -> list[IncidentTask]:
        """Oldest first (UUIDv7 order), keyset page after `after_id`."""
        query = select(IncidentTask).where(IncidentTask.incident_id == incident_id)
        if after_id is not None:
            query = query.where(IncidentTask.id > after_id)
        tasks = await session.scalars(query.order_by(IncidentTask.id).limit(limit))
        return list(tasks)
