"""Read, set and clear an incident's custom field values (MPS-20.28).

Values can change while the incident is not closed, cancelled or merged. Reading lists
every value, including values of fields archived since (MPS-8A.05 "existing values
stay"). Incident-writing roles change values; the visibility rule applies as for every
incident read.
"""

import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.incident.field_model import CustomFieldDefinition
from relyxus_api.modules.incident.field_repository import CustomFieldRepository
from relyxus_api.modules.incident.field_value_model import IncidentFieldValue
from relyxus_api.modules.incident.field_value_repository import FieldValueRepository
from relyxus_api.modules.incident.field_value_writer import FieldValueWriter
from relyxus_api.modules.incident.lifecycle import TERMINAL_LIFECYCLE_STATES, IncidentLifecycleState
from relyxus_api.modules.incident.model import Incident
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.service import IncidentNotFoundError
from relyxus_api.modules.incident.update_service import IncidentNotEditableError
from relyxus_api.shared.errors.app_errors import NotFoundError


class FieldValueNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_FIELD_VALUE_NOT_FOUND"


@dataclass(frozen=True, slots=True)
class FieldValue:
    value: IncidentFieldValue
    field: CustomFieldDefinition


class IncidentFieldValueService:
    def __init__(
        self,
        incidents: IncidentRepository | None = None,
        fields: CustomFieldRepository | None = None,
        values: FieldValueRepository | None = None,
        writer: FieldValueWriter | None = None,
    ) -> None:
        self._incidents = incidents or IncidentRepository()
        self._fields = fields or CustomFieldRepository()
        self._values = values or FieldValueRepository()
        self._writer = writer or FieldValueWriter()

    async def list(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> list[FieldValue]:
        incident = await self._incidents.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        values = await self._values.list_for_incident(session, incident_id)
        result = []
        for value in values:
            found = await self._fields.find_in_workspace(
                session, access.workspace_id, value.field_id
            )
            if found is not None:
                result.append(FieldValue(value=value, field=found))
        return result

    async def set(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        key: str,
        raw: Any,
    ) -> FieldValue:
        incident = await self._lock_open(session, access, incident_id)
        found = await self._writer.active_field(session, access.workspace_id, key)
        value = await self._writer.set_value(session, access, incident, found, raw)
        return FieldValue(value=value, field=found)

    async def clear(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID, key: str
    ) -> None:
        incident = await self._lock_open(session, access, incident_id)
        found = await self._fields.find_by_key(session, access.workspace_id, key)
        if found is None or not await self._writer.clear(session, access, incident, found):
            raise FieldValueNotFoundError(f"The incident has no value for '{key}'.")

    async def _lock_open(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> Incident:
        incident = await self._incidents.lock_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        if IncidentLifecycleState(incident.lifecycle_state) in TERMINAL_LIFECYCLE_STATES:
            raise IncidentNotEditableError(
                f"Fields of a {incident.lifecycle_state} incident can no longer change."
            )
        return incident
