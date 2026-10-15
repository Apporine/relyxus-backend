"""The custom-field library (MPS-8A.03, MPS-8A.04, MPS-8A.05, MPS-8A.06, MPS-20.27).

Owners and admins define fields; every member reads them. A field's key and data type
never change (existing values depend on them). Choice fields need at least one option,
with unique values; other types take none. Display conditions name incident types of
this workspace and/or severities. Every change bumps the field version, writes a
configuration version and an audit entry. Archiving is the only way to delete: values
already set stay.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.audit.model import ActorType, AuditOutcome
from relyxus_api.modules.audit.service import AuditService, NewAuditEvent
from relyxus_api.modules.configuration.model import ConfigurationObjectType
from relyxus_api.modules.configuration.service import (
    ConfigurationChange,
    ConfigurationVersionService,
)
from relyxus_api.modules.incident.field_model import (
    CHOICE_TYPES,
    CustomFieldDefinition,
    FieldDataType,
)
from relyxus_api.modules.incident.field_repository import MAX_ACTIVE_FIELDS, CustomFieldRepository
from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.model import IncidentSeverity
from relyxus_api.modules.incident.type_repository import IncidentTypeRepository
from relyxus_api.shared.errors.app_errors import ConflictError, NotFoundError, ValidationFailedError
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.id_cursor import decode_id_cursor
from relyxus_api.shared.http.pagination import Page, PageRequest, build_page
from relyxus_api.shared.http.preconditions import assert_if_match
from relyxus_api.shared.observability.correlation import get_correlation_id
from relyxus_api.shared.utils.ids import new_uuid7

FIELD_TARGET_TYPE = "custom_field"
FIELD_CREATED_ACTION = "custom_field.created"
FIELD_UPDATED_ACTION = "custom_field.updated"


class CustomFieldNotFoundError(NotFoundError):
    code: ClassVar[str] = "CUSTOM_FIELD_NOT_FOUND"


class CustomFieldKeyTakenError(ConflictError):
    code: ClassVar[str] = "CUSTOM_FIELD_KEY_TAKEN"


class CustomFieldInvalidError(ValidationFailedError):
    code: ClassVar[str] = "CUSTOM_FIELD_INVALID"


class NoCustomFieldChangesError(ValidationFailedError):
    code: ClassVar[str] = "CUSTOM_FIELD_NO_CHANGES"


@dataclass(frozen=True, slots=True)
class FieldOption:
    value: str
    label: str


@dataclass(frozen=True, slots=True)
class DisplayCondition:
    """Empty means "any"; both must match when both are set (MPS-8A.04)."""

    incident_type_ids: tuple[uuid.UUID, ...] = ()
    severities: tuple[IncidentSeverity, ...] = ()


@dataclass(frozen=True, slots=True)
class NewCustomField:
    key: str
    label: str
    description: str | None
    data_type: FieldDataType
    options: tuple[FieldOption, ...] = ()
    display_condition: DisplayCondition = field(default_factory=DisplayCondition)
    required_at_stage: IncidentLifecycleState | None = None


@dataclass(frozen=True, slots=True)
class CustomFieldChanges:
    changed_fields: frozenset[str]
    label: str | None = None
    description: str | None = None
    options: tuple[FieldOption, ...] | None = None
    display_condition: DisplayCondition | None = None
    required_at_stage: IncidentLifecycleState | None = None
    is_archived: bool | None = None
    if_match: str | None = None


class CustomFieldService:
    def __init__(
        self,
        repository: CustomFieldRepository | None = None,
        types: IncidentTypeRepository | None = None,
        audit: AuditService | None = None,
        versions: ConfigurationVersionService | None = None,
    ) -> None:
        self._repository = repository or CustomFieldRepository()
        self._types = types or IncidentTypeRepository()
        self._audit = audit or AuditService()
        self._versions = versions or ConfigurationVersionService()

    async def create(
        self, session: AsyncSession, access: WorkspaceAccess, new_field: NewCustomField
    ) -> CustomFieldDefinition:
        if await self._repository.find_by_key(session, access.workspace_id, new_field.key):
            raise CustomFieldKeyTakenError(f"A custom field with key '{new_field.key}' exists.")
        if (
            len(await self._repository.list_active(session, access.workspace_id))
            >= MAX_ACTIVE_FIELDS
        ):
            raise CustomFieldInvalidError(
                f"A workspace can have at most {MAX_ACTIVE_FIELDS} active custom fields."
            )
        _check_options(new_field.data_type, new_field.options)
        await self._check_condition(session, access, new_field.display_condition)
        created = await self._repository.save(
            session,
            CustomFieldDefinition(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                key=new_field.key,
                label=new_field.label,
                description=new_field.description,
                data_type=new_field.data_type.value,
                options=_options_json(new_field.options),
                display_condition=_condition_json(new_field.display_condition),
                required_at_stage=(
                    None
                    if new_field.required_at_stage is None
                    else new_field.required_at_stage.value
                ),
                version=1,
            ),
        )
        await self._record(session, access, created, FIELD_CREATED_ACTION, None)
        return created

    async def get(
        self, session: AsyncSession, access: WorkspaceAccess, field_id: uuid.UUID
    ) -> CustomFieldDefinition:
        found = await self._repository.find_in_workspace(session, access.workspace_id, field_id)
        if found is None:
            raise CustomFieldNotFoundError("No custom field with this ID in this workspace.")
        return found

    async def list(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        include_archived: bool,
        page_request: PageRequest,
    ) -> Page[CustomFieldDefinition]:
        fetched = await self._repository.list_in_workspace(
            session,
            access.workspace_id,
            include_archived,
            decode_id_cursor(page_request),
            page_request.limit + 1,
        )
        return build_page(fetched, page_request, lambda found: (str(found.id),))

    async def update(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        field_id: uuid.UUID,
        changes: CustomFieldChanges,
    ) -> CustomFieldDefinition:
        found = await self._repository.find_in_workspace(
            session, access.workspace_id, field_id, is_locking=True
        )
        if found is None:
            raise CustomFieldNotFoundError("No custom field with this ID in this workspace.")
        assert_if_match(format_weak_etag(found.id, found.updated_at), changes.if_match)
        fields = changes.changed_fields
        if "options" in fields and changes.options is not None:
            _check_options(FieldDataType(found.data_type), changes.options)
        if "display_condition" in fields and changes.display_condition is not None:
            await self._check_condition(session, access, changes.display_condition)
        before = _snapshot(found)
        _apply(found, changes)
        if _snapshot(found) == before:
            raise NoCustomFieldChangesError("The request does not change the custom field.")
        found.version += 1
        found = await self._repository.save(session, found)
        await self._record(session, access, found, FIELD_UPDATED_ACTION, before)
        return found

    async def _check_condition(
        self, session: AsyncSession, access: WorkspaceAccess, condition: DisplayCondition
    ) -> None:
        for type_id in condition.incident_type_ids:
            if await self._types.find_in_workspace(session, access.workspace_id, type_id) is None:
                raise CustomFieldInvalidError(
                    "Display conditions can only name incident types of this workspace."
                )

    async def _record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        found: CustomFieldDefinition,
        action: str,
        before: dict[str, object] | None,
    ) -> None:
        after = _snapshot(found)
        await self._audit.append(
            session,
            NewAuditEvent(
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                actor_type=ActorType.USER,
                actor_user_id=access.user_id,
                effective_user_id=None,
                action=action,
                target_type=FIELD_TARGET_TYPE,
                target_id=str(found.id),
                outcome=AuditOutcome.SUCCEEDED,
                before_state=before,
                after_state=after,
                correlation_id=get_correlation_id(),
            ),
        )
        await self._versions.record(
            session,
            access,
            ConfigurationChange(ConfigurationObjectType.CUSTOM_FIELD, found.id, before, after),
        )


def _check_options(data_type: FieldDataType, options: tuple[FieldOption, ...]) -> None:
    if data_type in CHOICE_TYPES:
        if not options:
            raise CustomFieldInvalidError("Choice fields need at least one option.")
        if len({option.value for option in options}) != len(options):
            raise CustomFieldInvalidError("Option values must be unique.")
    elif options:
        raise CustomFieldInvalidError("Only choice fields take options.")


def _options_json(options: tuple[FieldOption, ...]) -> list[dict[str, object]]:
    return [{"value": option.value, "label": option.label} for option in options]


def _condition_json(condition: DisplayCondition) -> dict[str, object]:
    return {
        "incident_type_ids": [
            str(type_id) for type_id in dict.fromkeys(condition.incident_type_ids)
        ],
        "severities": [
            severity.value for severity in IncidentSeverity if severity in condition.severities
        ],
    }


def _apply(found: CustomFieldDefinition, changes: CustomFieldChanges) -> None:
    fields = changes.changed_fields
    if "label" in fields and changes.label is not None:
        found.label = changes.label
    if "description" in fields:
        found.description = changes.description
    if "options" in fields and changes.options is not None:
        found.options = _options_json(changes.options)
    if "display_condition" in fields and changes.display_condition is not None:
        found.display_condition = _condition_json(changes.display_condition)
    if "required_at_stage" in fields:
        found.required_at_stage = (
            None if changes.required_at_stage is None else changes.required_at_stage.value
        )
    if "is_archived" in fields and changes.is_archived is not None:
        is_archived = found.archived_at is not None
        if changes.is_archived and not is_archived:
            found.archived_at = datetime.now(UTC)
        elif not changes.is_archived and is_archived:
            found.archived_at = None


def _snapshot(found: CustomFieldDefinition) -> dict[str, object]:
    return {
        "key": found.key,
        "label": found.label,
        "description": found.description,
        "data_type": found.data_type,
        "options": list(found.options),
        "display_condition": dict(found.display_condition),
        "required_at_stage": found.required_at_stage,
        "is_archived": found.archived_at is not None,
    }
