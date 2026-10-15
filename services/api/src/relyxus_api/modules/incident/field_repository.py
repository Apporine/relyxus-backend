"""Custom field definition persistence. Queries only; rules live in the field service."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.field_model import CustomFieldDefinition

# Bound on the active fields a workspace defines; reads of "all fields" rely on it.
MAX_ACTIVE_FIELDS = 200


class CustomFieldRepository:
    async def save(
        self, session: AsyncSession, field: CustomFieldDefinition
    ) -> CustomFieldDefinition:
        session.add(field)
        await session.flush()
        await session.refresh(field)
        return field

    async def find_by_key(
        self, session: AsyncSession, workspace_id: uuid.UUID, key: str
    ) -> CustomFieldDefinition | None:
        found: CustomFieldDefinition | None = await session.scalar(
            select(CustomFieldDefinition).where(
                CustomFieldDefinition.workspace_id == workspace_id,
                CustomFieldDefinition.key == key,
            )
        )
        return found

    async def find_in_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        field_id: uuid.UUID,
        *,
        is_locking: bool = False,
    ) -> CustomFieldDefinition | None:
        query = select(CustomFieldDefinition).where(
            CustomFieldDefinition.id == field_id,
            CustomFieldDefinition.workspace_id == workspace_id,
        )
        if is_locking:
            query = query.with_for_update()
        found: CustomFieldDefinition | None = await session.scalar(query)
        return found

    async def list_active(
        self, session: AsyncSession, workspace_id: uuid.UUID
    ) -> list[CustomFieldDefinition]:
        """Every active field, oldest first; bounded by MAX_ACTIVE_FIELDS."""
        fields = await session.scalars(
            select(CustomFieldDefinition)
            .where(
                CustomFieldDefinition.workspace_id == workspace_id,
                CustomFieldDefinition.archived_at.is_(None),
            )
            .order_by(CustomFieldDefinition.id)
            .limit(MAX_ACTIVE_FIELDS)
        )
        return list(fields)

    async def list_in_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        include_archived: bool,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[CustomFieldDefinition]:
        query = select(CustomFieldDefinition).where(
            CustomFieldDefinition.workspace_id == workspace_id
        )
        if not include_archived:
            query = query.where(CustomFieldDefinition.archived_at.is_(None))
        if after_id is not None:
            query = query.where(CustomFieldDefinition.id > after_id)
        fields = await session.scalars(query.order_by(CustomFieldDefinition.id).limit(limit))
        return list(fields)
