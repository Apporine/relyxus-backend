import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.model import TITLE_MAX_LENGTH, Incident, IncidentSeverity
from relyxus_api.modules.incident.role_model import IncidentRole, IncidentRoleAssignment

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
    number: int = Field(
        description="Per-workspace display number (e.g. shown as INC-42); not an identifier.",
        examples=[42],
    )
    title: str = Field(examples=["Card authorisations failing in EU"])
    severity: IncidentSeverity = Field(examples=[IncidentSeverity.SEV1])
    lifecycle_state: IncidentLifecycleState = Field(examples=[IncidentLifecycleState.INVESTIGATING])
    declared_at: datetime | None = Field(examples=["2026-10-15T07:56:00Z"])
    declared_by_user_id: uuid.UUID | None = Field(examples=["0192f0c4-0000-7000-8000-0000000000f1"])
    mitigated_at: datetime | None = Field(examples=[None])
    resolved_at: datetime | None = Field(examples=[None])
    closed_at: datetime | None = Field(examples=[None])
    cancelled_at: datetime | None = Field(examples=[None])
    merged_into_incident_id: uuid.UUID | None = Field(examples=[None])
    created_at: datetime = Field(examples=["2026-10-15T07:55:41Z"])
    updated_at: datetime = Field(examples=["2026-10-15T07:56:00Z"])

    @classmethod
    def from_incident(cls, incident: Incident) -> "IncidentView":
        return cls(
            id=incident.id,
            workspace_id=incident.workspace_id,
            number=incident.number,
            title=incident.title,
            severity=IncidentSeverity(incident.severity),
            lifecycle_state=IncidentLifecycleState(incident.lifecycle_state),
            declared_at=incident.declared_at,
            declared_by_user_id=incident.declared_by_user_id,
            mitigated_at=incident.mitigated_at,
            resolved_at=incident.resolved_at,
            closed_at=incident.closed_at,
            cancelled_at=incident.cancelled_at,
            merged_into_incident_id=incident.merged_into_incident_id,
            created_at=incident.created_at,
            updated_at=incident.updated_at,
        )


REASON_MAX_LENGTH = 1000
TransitionReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=REASON_MAX_LENGTH)
]


class TransitionIncidentRequest(BaseModel):
    """Move an incident through its lifecycle (MPS-8A.09-8A.16, ADR-0004)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_state: IncidentLifecycleState = Field(examples=[IncidentLifecycleState.MITIGATING])
    reason: TransitionReason | None = Field(
        default=None,
        description="Required to cancel (false alarm, duplicate) and to reopen.",
        examples=["Duplicate of the EU card authorisation incident"],
    )
    merged_into_incident_id: uuid.UUID | None = Field(
        default=None,
        description="Required when target_state is merged; an open incident in this workspace.",
        examples=["0192f0c4-7d1e-7a3b-9c2d-5e6f7a8b9c0d"],
    )


class UpdateIncidentRequest(BaseModel):
    """Change an open incident's title and/or severity (MPS-8.06)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: IncidentTitle | None = Field(
        default=None, examples=["Card authorisations failing in EU"]
    )
    severity: IncidentSeverity | None = Field(default=None, examples=[IncidentSeverity.SEV1])
    reason: TransitionReason | None = Field(
        default=None,
        description="Required when severity changes (human override, MPS-8.06).",
        examples=["Failed payments now above 500 a minute"],
    )


class AssignIncidentRoleRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: uuid.UUID = Field(examples=["0192f0c4-0000-7000-8000-0000000000f1"])


class IncidentRoleView(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: IncidentRole = Field(examples=[IncidentRole.INCIDENT_COMMANDER])
    user_id: uuid.UUID = Field(examples=["0192f0c4-0000-7000-8000-0000000000f1"])
    assigned_by_user_id: uuid.UUID = Field(examples=["0192f0c4-0000-7000-8000-0000000000f2"])
    assigned_at: datetime = Field(examples=["2026-10-15T08:01:00Z"])

    @classmethod
    def from_assignment(cls, assignment: IncidentRoleAssignment) -> "IncidentRoleView":
        return cls(
            role=IncidentRole(assignment.role),
            user_id=assignment.user_id,
            assigned_by_user_id=assignment.assigned_by_user_id,
            assigned_at=assignment.updated_at,
        )
