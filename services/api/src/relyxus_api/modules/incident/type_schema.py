import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from relyxus_api.modules.incident.model import IncidentSeverity, IncidentVisibility
from relyxus_api.modules.incident.type_model import (
    TYPE_DESCRIPTION_MAX_LENGTH,
    TYPE_KEY_PATTERN,
    TYPE_NAME_MAX_LENGTH,
    IncidentType,
)

TypeName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TYPE_NAME_MAX_LENGTH)
]
TypeDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=TYPE_DESCRIPTION_MAX_LENGTH)
]
Severities = Annotated[list[IncidentSeverity], Field(min_length=1, max_length=4)]


class CreateIncidentTypeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[str, StringConstraints(pattern=TYPE_KEY_PATTERN)] = Field(
        description="Stable identifier, unique in the workspace.", examples=["payment-incident"]
    )
    name: TypeName = Field(examples=["Payment incident"])
    description: TypeDescription | None = None
    allowed_severities: Severities = Field(
        default_factory=lambda: list(IncidentSeverity), examples=[["sev1", "sev2"]]
    )
    default_severity: IncidentSeverity = Field(
        description="Must be one of `allowed_severities`.", examples=[IncidentSeverity.SEV2]
    )
    default_visibility: IncidentVisibility = Field(default=IncidentVisibility.WORKSPACE)


class UpdateIncidentTypeRequest(BaseModel):
    """Partial update; every change creates a new type version. The key never changes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: TypeName | None = None
    description: TypeDescription | None = None
    allowed_severities: Severities | None = None
    default_severity: IncidentSeverity | None = None
    default_visibility: IncidentVisibility | None = None
    is_archived: bool | None = Field(
        default=None, description="Archived types cannot be used to declare new incidents."
    )


class IncidentTypeView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    key: str
    name: str
    description: str | None
    allowed_severities: list[IncidentSeverity]
    default_severity: IncidentSeverity
    default_visibility: IncidentVisibility
    version: int = Field(description="Current configuration version; incidents keep theirs.")
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_type(cls, incident_type: IncidentType) -> "IncidentTypeView":
        return cls(
            id=incident_type.id,
            key=incident_type.key,
            name=incident_type.name,
            description=incident_type.description,
            allowed_severities=[IncidentSeverity(v) for v in incident_type.allowed_severities],
            default_severity=IncidentSeverity(incident_type.default_severity),
            default_visibility=IncidentVisibility(incident_type.default_visibility),
            version=incident_type.version,
            archived_at=incident_type.archived_at,
            created_at=incident_type.created_at,
            updated_at=incident_type.updated_at,
        )
