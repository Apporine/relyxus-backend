"""Custom field value persistence. Queries only; rules live in field_value_rules."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.field_repository import MAX_ACTIVE_FIELDS
from relyxus_api.modules.incident.field_value_model import IncidentFieldValue


class FieldValueRepository:
    async def save(self, session: AsyncSession, value: IncidentFieldValue) -> IncidentFieldValue:
        session.add(value)
        await session.flush()
        await session.refresh(value)
        return value

    async def find(
        self, session: AsyncSession, incident_id: uuid.UUID, field_id: uuid.UUID
    ) -> IncidentFieldValue | None:
        found: IncidentFieldValue | None = await session.scalar(
            select(IncidentFieldValue).where(
                IncidentFieldValue.incident_id == incident_id,
                IncidentFieldValue.field_id == field_id,
            )
        )
        return found

    async def list_for_incident(
        self, session: AsyncSession, incident_id: uuid.UUID
    ) -> list[IncidentFieldValue]:
        """Values of archived fields included; bounded by the field limit times two."""
        values = await session.scalars(
            select(IncidentFieldValue)
            .where(IncidentFieldValue.incident_id == incident_id)
            .order_by(IncidentFieldValue.id)
            .limit(MAX_ACTIVE_FIELDS * 2)
        )
        return list(values)

    async def remove(self, session: AsyncSession, value_id: uuid.UUID) -> None:
        await session.execute(delete(IncidentFieldValue).where(IncidentFieldValue.id == value_id))
