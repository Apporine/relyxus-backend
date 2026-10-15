import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.model import TITLE_MAX_LENGTH, Incident, IncidentSeverity

IncidentTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX_LENGTH)
]


class DeclareIncidentRequest(BaseModel):
    """Declare an incident, or save it as a triage draft (MPS-15.04 "Declare / Save draft")."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: IncidentTitle = Field(examples=["Card authorisations failing in EU"])
    severity: IncidentSeverity = Field(examples=[IncidentSeverity.SEV1])
    is_declared: bool = Field(
        default=True,
        description="False saves a draft that stays in triage instead of declaring it.",
        examples=[True],
    )


class IncidentView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(examples=["0192f0c4-7d1e-7a3b-9c2d-5e6f7a8b9c0d"])
    workspace_id: uuid.UUID = Field(examples=["0192f0c4-0000-7000-8000-0000000000a1"])
    title: str = Field(examples=["Card authorisations failing in EU"])
    severity: IncidentSeverity = Field(examples=[IncidentSeverity.SEV1])
    lifecycle_state: IncidentLifecycleState = Field(examples=[IncidentLifecycleState.INVESTIGATING])
    declared_at: datetime | None = Field(examples=["2026-10-15T07:56:00Z"])
    declared_by_user_id: uuid.UUID | None = Field(examples=["0192f0c4-0000-7000-8000-0000000000f1"])
    created_at: datetime = Field(examples=["2026-10-15T07:55:41Z"])
    updated_at: datetime = Field(examples=["2026-10-15T07:56:00Z"])

    @classmethod
    def from_incident(cls, incident: Incident) -> "IncidentView":
        return cls(
            id=incident.id,
            workspace_id=incident.workspace_id,
            title=incident.title,
            severity=IncidentSeverity(incident.severity),
            lifecycle_state=IncidentLifecycleState(incident.lifecycle_state),
            declared_at=incident.declared_at,
            declared_by_user_id=incident.declared_by_user_id,
            created_at=incident.created_at,
            updated_at=incident.updated_at,
        )
