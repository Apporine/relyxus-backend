"""Write custom field values and check required fields (MPS-8A.04, MPS-20.28).

Shared by declaration, lifecycle transitions and the field endpoints. Callers hold the
incident row lock. Each set or clear is audited and on the timeline with the field
version it was made under.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.field_model import CustomFieldDefinition
from relyxus_api.modules.incident.field_repository import CustomFieldRepository
from relyxus_api.modules.incident.field_value_model import IncidentFieldValue
from relyxus_api.modules.incident.field_value_repository import FieldValueRepository
from relyxus_api.modules.incident.field_value_rules import (
    FieldNotApplicableError,
    FieldValueInvalidError,
    FieldValueValidator,
    is_applicable,
    require_complete,
)
from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.model import Incident
from relyxus_api.shared.utils.ids import new_uuid7

FIELD_SET_ACTION = "incident.field_set"
FIELD_CLEARED_ACTION = "incident.field_cleared"
FIELD_SUBJECT_TYPE = "incident_field"


class FieldValueWriter:
    def __init__(
        self,
        fields: CustomFieldRepository | None = None,
        values: FieldValueRepository | None = None,
        validator: FieldValueValidator | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._fields = fields or CustomFieldRepository()
        self._values = values or FieldValueRepository()
        self._validator = validator or FieldValueValidator()
        self._activity = activity or IncidentActivityRecorder()

    async def active_field(
        self, session: AsyncSession, workspace_id: uuid.UUID, key: str
    ) -> CustomFieldDefinition:
        found = await self._fields.find_by_key(session, workspace_id, key)
        if found is None or found.archived_at is not None:
            raise FieldValueInvalidError(f"There is no active custom field '{key}'.")
        return found

    async def set_many(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident: Incident,
        raw_values: dict[str, Any],
    ) -> None:
        for key, raw in raw_values.items():
            found = await self.active_field(session, access.workspace_id, key)
            await self.set_value(session, access, incident, found, raw)

    async def set_value(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident: Incident,
        found: CustomFieldDefinition,
        raw: Any,
    ) -> IncidentFieldValue:
        if not is_applicable(found, incident):
            raise FieldNotApplicableError(
                f"'{found.key}' does not apply to this incident's type and severity."
            )
        value = await self._validator.normalise(session, access.workspace_id, found, raw)
        current = await self._values.find(session, incident.id, found.id)
        before = None if current is None else {"key": found.key, "value": current.value}
        if current is None:
            current = IncidentFieldValue(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                incident_id=incident.id,
                field_id=found.id,
                field_version=found.version,
                value=value,
                set_by_user_id=access.user_id,
            )
        elif current.value == value:
            return current
        else:
            current.value = value
            current.field_version = found.version
            current.set_by_user_id = access.user_id
        current = await self._values.save(session, current)
        await self._activity.record(
            session,
            access,
            _activity(
                incident.id,
                FIELD_SET_ACTION,
                current.field_id,
                before,
                {"key": found.key, "value": value, "field_version": found.version},
            ),
        )
        return current

    async def clear(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident: Incident,
        found: CustomFieldDefinition,
    ) -> bool:
        """False when there was no value to clear."""
        current = await self._values.find(session, incident.id, found.id)
        if current is None:
            return False
        await self._values.remove(session, current.id)
        await self._activity.record(
            session,
            access,
            _activity(
                incident.id,
                FIELD_CLEARED_ACTION,
                found.id,
                {"key": found.key, "value": current.value},
                None,
            ),
        )
        return True

    async def require_complete(
        self,
        session: AsyncSession,
        incident: Incident,
        target: IncidentLifecycleState,
    ) -> None:
        """Raise when an applicable field required by `target` has no value."""
        fields = await self._fields.list_active(session, incident.workspace_id)
        if not any(found.required_at_stage for found in fields):
            return
        filled = {
            value.field_id for value in await self._values.list_for_incident(session, incident.id)
        }
        require_complete(fields, incident, filled, target)


def _activity(
    incident_id: uuid.UUID,
    action: str,
    field_id: uuid.UUID,
    before: dict[str, object] | None,
    after: dict[str, object] | None,
) -> IncidentActivity:
    return IncidentActivity(
        incident_id=incident_id,
        action=action,
        subject_type=FIELD_SUBJECT_TYPE,
        subject_id=field_id,
        before=before,
        after=after,
    )
