"""Incident types: configurable without code (MPS-8A.01, MPS-8A.02, MPS-8A.06, MPS-20.26).

Owners and admins create, change and archive types; every member reads them. A type's
key never changes. Every change bumps the type's version and writes a configuration
version in the same transaction, so an incident can always be traced to the exact type
configuration it was declared under. The default severity must be one of the allowed
severities. `install_defaults` adds the nine default types of MPS-8A.02 that the
workspace does not have yet (by key); their default severities are provisional (Q-43).
"""

import uuid
from dataclasses import dataclass
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
from relyxus_api.modules.incident.model import IncidentSeverity, IncidentVisibility
from relyxus_api.modules.incident.type_model import IncidentType
from relyxus_api.modules.incident.type_repository import IncidentTypeRepository
from relyxus_api.shared.errors.app_errors import ConflictError, NotFoundError, ValidationFailedError
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.id_cursor import decode_id_cursor
from relyxus_api.shared.http.pagination import Page, PageRequest, build_page
from relyxus_api.shared.http.preconditions import assert_if_match
from relyxus_api.shared.observability.correlation import get_correlation_id
from relyxus_api.shared.utils.ids import new_uuid7

TYPE_TARGET_TYPE = "incident_type"
TYPE_CREATED_ACTION = "incident_type.created"
TYPE_UPDATED_ACTION = "incident_type.updated"
_ALL_SEVERITIES = tuple(IncidentSeverity)
_SEV = IncidentSeverity
_VIS = IncidentVisibility


class IncidentTypeNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_TYPE_NOT_FOUND"


class IncidentTypeKeyTakenError(ConflictError):
    code: ClassVar[str] = "INCIDENT_TYPE_KEY_TAKEN"


class DefaultSeverityNotAllowedError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_TYPE_DEFAULT_SEVERITY_NOT_ALLOWED"


class NoIncidentTypeChangesError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_TYPE_NO_CHANGES"


@dataclass(frozen=True, slots=True)
class NewIncidentType:
    key: str
    name: str
    description: str | None
    allowed_severities: tuple[IncidentSeverity, ...]
    default_severity: IncidentSeverity
    default_visibility: IncidentVisibility


@dataclass(frozen=True, slots=True)
class IncidentTypeChanges:
    changed_fields: frozenset[str]
    name: str | None = None
    description: str | None = None
    allowed_severities: tuple[IncidentSeverity, ...] | None = None
    default_severity: IncidentSeverity | None = None
    default_visibility: IncidentVisibility | None = None
    is_archived: bool | None = None
    if_match: str | None = None


# MPS-8A.02 default editable types. Visibility defaults come from the spec; default
# severities are provisional (register Q-43).
DEFAULT_TYPES: tuple[NewIncidentType, ...] = tuple(
    NewIncidentType(key, name, None, _ALL_SEVERITIES, severity, visibility)
    for key, name, severity, visibility in (
        ("production-outage", "Production outage", _SEV.SEV2, _VIS.WORKSPACE),
        ("degraded-performance", "Degraded performance", _SEV.SEV3, _VIS.WORKSPACE),
        ("payment-incident", "Payment incident", _SEV.SEV2, _VIS.WORKSPACE),
        ("security-event", "Security event", _SEV.SEV2, _VIS.INVITE_ONLY),
        ("third-party-outage", "Third-party outage", _SEV.SEV3, _VIS.WORKSPACE),
        ("data-incident", "Data incident", _SEV.SEV2, _VIS.RESTRICTED),
        ("regulatory-reportable", "Regulatory reportable incident", _SEV.SEV2, _VIS.WORKSPACE),
        ("exercise-or-drill", "Exercise or drill", _SEV.SEV4, _VIS.WORKSPACE),
        ("internal-operational-event", "Internal operational event", _SEV.SEV4, _VIS.WORKSPACE),
    )
)


class IncidentTypeService:
    def __init__(
        self,
        repository: IncidentTypeRepository | None = None,
        audit: AuditService | None = None,
        versions: ConfigurationVersionService | None = None,
    ) -> None:
        self._repository = repository or IncidentTypeRepository()
        self._audit = audit or AuditService()
        self._versions = versions or ConfigurationVersionService()

    async def create(
        self, session: AsyncSession, access: WorkspaceAccess, new_type: NewIncidentType
    ) -> IncidentType:
        if await self._repository.find_by_key(session, access.workspace_id, new_type.key):
            raise IncidentTypeKeyTakenError(f"An incident type with key '{new_type.key}' exists.")
        _require_default_allowed(new_type.allowed_severities, new_type.default_severity)
        incident_type = await self._repository.save(
            session,
            IncidentType(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                key=new_type.key,
                name=new_type.name,
                description=new_type.description,
                allowed_severities=_ordered(new_type.allowed_severities),
                default_severity=new_type.default_severity.value,
                default_visibility=new_type.default_visibility.value,
                version=1,
            ),
        )
        await self._record(session, access, incident_type, TYPE_CREATED_ACTION, None)
        return incident_type

    async def install_defaults(
        self, session: AsyncSession, access: WorkspaceAccess
    ) -> list[IncidentType]:
        """Create the default types the workspace lacks; existing keys are left untouched."""
        created = []
        for default in DEFAULT_TYPES:
            if await self._repository.find_by_key(session, access.workspace_id, default.key):
                continue
            created.append(await self.create(session, access, default))
        return created

    async def get(
        self, session: AsyncSession, access: WorkspaceAccess, type_id: uuid.UUID
    ) -> IncidentType:
        found = await self._repository.find_in_workspace(session, access.workspace_id, type_id)
        if found is None:
            raise IncidentTypeNotFoundError("No incident type with this ID in this workspace.")
        return found

    async def list(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        include_archived: bool,
        page_request: PageRequest,
    ) -> Page[IncidentType]:
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
        type_id: uuid.UUID,
        changes: IncidentTypeChanges,
    ) -> IncidentType:
        incident_type = await self._repository.find_in_workspace(
            session, access.workspace_id, type_id, is_locking=True
        )
        if incident_type is None:
            raise IncidentTypeNotFoundError("No incident type with this ID in this workspace.")
        assert_if_match(
            format_weak_etag(incident_type.id, incident_type.updated_at), changes.if_match
        )
        before = _snapshot(incident_type)
        _apply(incident_type, changes)
        _require_default_allowed(
            tuple(IncidentSeverity(value) for value in incident_type.allowed_severities),
            IncidentSeverity(incident_type.default_severity),
        )
        if _snapshot(incident_type) == before:
            raise NoIncidentTypeChangesError("The request does not change the incident type.")
        incident_type.version += 1
        incident_type = await self._repository.save(session, incident_type)
        await self._record(session, access, incident_type, TYPE_UPDATED_ACTION, before)
        return incident_type

    async def _record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_type: IncidentType,
        action: str,
        before: dict[str, object] | None,
    ) -> None:
        after = _snapshot(incident_type)
        await self._audit.append(
            session,
            NewAuditEvent(
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                actor_type=ActorType.USER,
                actor_user_id=access.user_id,
                effective_user_id=None,
                action=action,
                target_type=TYPE_TARGET_TYPE,
                target_id=str(incident_type.id),
                outcome=AuditOutcome.SUCCEEDED,
                before_state=before,
                after_state=after,
                correlation_id=get_correlation_id(),
            ),
        )
        await self._versions.record(
            session,
            access,
            ConfigurationChange(
                ConfigurationObjectType.INCIDENT_TYPE, incident_type.id, before, after
            ),
        )


def _require_default_allowed(
    allowed: tuple[IncidentSeverity, ...], default: IncidentSeverity
) -> None:
    if default not in allowed:
        raise DefaultSeverityNotAllowedError(
            "The default severity must be one of the allowed severities."
        )


def _ordered(severities: tuple[IncidentSeverity, ...]) -> list[str]:
    """Distinct, in SEV1-to-SEV4 order, so equal sets compare equal."""
    return [severity.value for severity in IncidentSeverity if severity in severities]


def _apply(incident_type: IncidentType, changes: IncidentTypeChanges) -> None:
    fields = changes.changed_fields
    if "name" in fields and changes.name is not None:
        incident_type.name = changes.name
    if "description" in fields:
        incident_type.description = changes.description
    if "allowed_severities" in fields and changes.allowed_severities is not None:
        incident_type.allowed_severities = _ordered(changes.allowed_severities)
    if "default_severity" in fields and changes.default_severity is not None:
        incident_type.default_severity = changes.default_severity.value
    if "default_visibility" in fields and changes.default_visibility is not None:
        incident_type.default_visibility = changes.default_visibility.value
    if "is_archived" in fields and changes.is_archived is not None:
        is_archived = incident_type.archived_at is not None
        if changes.is_archived and not is_archived:
            incident_type.archived_at = datetime.now(UTC)
        elif not changes.is_archived and is_archived:
            incident_type.archived_at = None


def _snapshot(incident_type: IncidentType) -> dict[str, object]:
    return {
        "key": incident_type.key,
        "name": incident_type.name,
        "description": incident_type.description,
        "allowed_severities": list(incident_type.allowed_severities),
        "default_severity": incident_type.default_severity,
        "default_visibility": incident_type.default_visibility,
        "is_archived": incident_type.archived_at is not None,
    }
