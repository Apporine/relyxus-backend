"""Rules that tie incidents to their type (MPS-8A.08, MPS-8A.06, MPS-20.12; register Q-44).

At declaration: once a workspace has an active incident type, every new incident needs
one; archived types cannot be used. The type supplies the default severity and
visibility, and the severity must be one the type allows. The incident records the type
and the type version it was declared under, so later type edits never change it.

Afterwards: severity changes are checked against the allowed severities of the type
version the incident was declared under, read from that configuration version.
"""

import uuid
from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.configuration.model import ConfigurationObjectType
from relyxus_api.modules.configuration.repository import ConfigurationVersionRepository
from relyxus_api.modules.incident.model import Incident, IncidentSeverity, IncidentVisibility
from relyxus_api.modules.incident.type_repository import IncidentTypeRepository
from relyxus_api.shared.errors.app_errors import ValidationFailedError


class IncidentTypeRequiredError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_TYPE_REQUIRED"


class IncidentTypeInvalidError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_TYPE_INVALID"


class SeverityRequiredError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_SEVERITY_REQUIRED"


class SeverityNotAllowedError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_SEVERITY_NOT_ALLOWED"


@dataclass(frozen=True, slots=True)
class Declaration:
    type_id: uuid.UUID | None
    type_version: int | None
    severity: IncidentSeverity
    visibility: IncidentVisibility


async def resolve_declaration(
    session: AsyncSession,
    types: IncidentTypeRepository,
    workspace_id: uuid.UUID,
    type_id: uuid.UUID | None,
    severity: IncidentSeverity | None,
    visibility: IncidentVisibility | None,
) -> Declaration:
    """`None` severity or visibility means "not given": the type's default applies."""
    if type_id is None:
        if await types.has_active(session, workspace_id):
            raise IncidentTypeRequiredError(
                "This workspace uses incident types; choose one to declare an incident."
            )
        if severity is None:
            raise SeverityRequiredError("A severity is required when no incident type is given.")
        return Declaration(None, None, severity, visibility or IncidentVisibility.WORKSPACE)

    incident_type = await types.find_in_workspace(session, workspace_id, type_id)
    if incident_type is None or incident_type.archived_at is not None:
        raise IncidentTypeInvalidError(
            "The incident type must be an active type of this workspace."
        )
    chosen = severity or IncidentSeverity(incident_type.default_severity)
    _require_allowed(chosen, incident_type.allowed_severities, incident_type.name)
    return Declaration(
        type_id=incident_type.id,
        type_version=incident_type.version,
        severity=chosen,
        visibility=visibility or IncidentVisibility(incident_type.default_visibility),
    )


async def require_severity_allowed(
    session: AsyncSession,
    versions: ConfigurationVersionRepository,
    incident: Incident,
    severity: IncidentSeverity,
) -> None:
    """Check against the type version the incident was declared under."""
    if incident.incident_type_id is None or incident.incident_type_version is None:
        return
    version = await versions.find(
        session,
        incident.workspace_id,
        ConfigurationObjectType.INCIDENT_TYPE.value,
        incident.incident_type_id,
        incident.incident_type_version,
    )
    if version is None:
        return
    allowed = version.snapshot.get("allowed_severities", [])
    _require_allowed(severity, allowed, str(version.snapshot.get("name", "this type")))


def _require_allowed(severity: IncidentSeverity, allowed: list[str], type_name: str) -> None:
    if severity.value not in allowed:
        raise SeverityNotAllowedError(
            f"{severity.value.upper()} is not allowed for {type_name} incidents "
            f"(allowed: {', '.join(value.upper() for value in allowed)})."
        )
