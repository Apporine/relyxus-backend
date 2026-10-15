import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.model import (
    ROOT_CAUSE_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    Incident,
    IncidentSeverity,
    IncidentVisibility,
)
from relyxus_api.modules.incident.role_model import IncidentRole, IncidentRoleAssignment

IncidentTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX_LENGTH)
]


class DeclareIncidentRequest(BaseModel):
    """Declare an incident, or save it as a triage draft (MPS-15.04 "Declare / Save draft")."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: IncidentTitle = Field(examples=["Card authorisations failing in EU"])
    incident_type_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Required once the workspace has incident types (MPS-8A.08). Supplies the "
            "default severity and visibility."
        ),
    )
    severity: IncidentSeverity | None = Field(
        default=None,
        description=(
            "Required without a type; with a type, defaults to the type's and must be allowed."
        ),
        examples=[IncidentSeverity.SEV1],
    )
    is_declared: bool = Field(
        default=True,
        description="False saves a draft that stays in triage instead of declaring it.",
        examples=[True],
    )
    impact_started_at: AwareDatetime | None = Field(
        default=None,
        description="When customer or business impact began, if known. Not after detected_at.",
        examples=["2026-10-15T07:41:00Z"],
    )
    detected_at: AwareDatetime | None = Field(
        default=None,
        description="When the problem was noticed; defaults to the time of this request.",
        examples=["2026-10-15T07:50:00Z"],
    )
    affected_service_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=50,
        description="Active services of this workspace the incident affects (MPS-8A.08).",
    )
    field_values: dict[str, Any] = Field(
        default_factory=dict,
        max_length=200,
        description=(
            "Custom field values by field key (MPS-8A.04). Fields required at "
            "`investigating` must be given to declare."
        ),
        examples=[{"affected_region": "eu_west"}],
    )
    visibility: IncidentVisibility | None = Field(
        default=None,
        description=(
            "Who can see the incident (MPS-8A.23); defaults to the type's, else `workspace`. "
            "Anything but `workspace` hides it from "
            "everyone except owners, its creator and role holders, and granted people."
        ),
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
    visibility: IncidentVisibility = Field(examples=[IncidentVisibility.WORKSPACE])
    incident_type_id: uuid.UUID | None = Field(examples=[None])
    incident_type_version: int | None = Field(
        description="The type's configuration version at declaration.", examples=[None]
    )
    lifecycle_state: IncidentLifecycleState = Field(examples=[IncidentLifecycleState.INVESTIGATING])
    impact_started_at: datetime | None = Field(examples=["2026-10-15T07:41:00Z"])
    detected_at: datetime | None = Field(examples=["2026-10-15T07:50:00Z"])
    acknowledged_at: datetime | None = Field(examples=["2026-10-15T07:52:00Z"])
    acknowledged_by_user_id: uuid.UUID | None = Field(
        examples=["0192f0c4-0000-7000-8000-0000000000f1"]
    )
    declared_at: datetime | None = Field(examples=["2026-10-15T07:56:00Z"])
    declared_by_user_id: uuid.UUID | None = Field(examples=["0192f0c4-0000-7000-8000-0000000000f1"])
    mitigated_at: datetime | None = Field(examples=[None])
    resolved_at: datetime | None = Field(examples=[None])
    closed_at: datetime | None = Field(examples=[None])
    closed_by_user_id: uuid.UUID | None = Field(examples=[None])
    root_cause: str | None = Field(
        description="Recorded at closing; required for SEV1/SEV2 (MPS-13.04).", examples=[None]
    )
    closure_exception_reason: str | None = Field(
        description="Set when an owner closed without the usual gates (MPS-13.17).",
        examples=[None],
    )
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
            visibility=IncidentVisibility(incident.visibility),
            incident_type_id=incident.incident_type_id,
            incident_type_version=incident.incident_type_version,
            lifecycle_state=IncidentLifecycleState(incident.lifecycle_state),
            impact_started_at=incident.impact_started_at,
            detected_at=incident.detected_at,
            acknowledged_at=incident.acknowledged_at,
            acknowledged_by_user_id=incident.acknowledged_by_user_id,
            declared_at=incident.declared_at,
            declared_by_user_id=incident.declared_by_user_id,
            mitigated_at=incident.mitigated_at,
            resolved_at=incident.resolved_at,
            closed_at=incident.closed_at,
            closed_by_user_id=incident.closed_by_user_id,
            root_cause=incident.root_cause,
            closure_exception_reason=incident.closure_exception_reason,
            cancelled_at=incident.cancelled_at,
            merged_into_incident_id=incident.merged_into_incident_id,
            created_at=incident.created_at,
            updated_at=incident.updated_at,
        )


REASON_MAX_LENGTH = 1000
TransitionReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=REASON_MAX_LENGTH)
]


RootCause = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=ROOT_CAUSE_MAX_LENGTH)
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
    root_cause: RootCause | None = Field(
        default=None,
        description="When closing: the root cause; required for SEV1/SEV2 (MPS-13.04).",
        examples=["Expired TLS certificate on the card processor gateway"],
    )
    closure_exception_reason: TransitionReason | None = Field(
        default=None,
        description=(
            "When closing: a workspace owner's reason to close without a signed-off review, "
            "finished tasks or complete mandatory follow-ups (MPS-13.17)."
        ),
    )


class UpdateIncidentRequest(BaseModel):
    """Change an open incident's title, severity or reported times (MPS-8.06, MPS-8A.20)."""

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
    impact_started_at: AwareDatetime | None = Field(
        default=None,
        description="Corrected start of impact. Not in the future, not after detected_at.",
        examples=["2026-10-15T07:38:00Z"],
    )
    detected_at: AwareDatetime | None = Field(
        default=None, description="Corrected detection time.", examples=["2026-10-15T07:49:00Z"]
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


class AffectedServiceView(BaseModel):
    model_config = ConfigDict(frozen=True)

    service_id: uuid.UUID
    key: str
    name: str
    tier: str
    added_by_user_id: uuid.UUID
    added_at: datetime


class SetFieldValueRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Any = Field(
        description=(
            "Shape depends on the field: text, number (number or decimal string), currency "
            "`{amount_minor, currency}`, ISO 8601 date-time with zone, true/false, an option "
            "value, a list of option values, a user/team/service ID, or an http(s) URL."
        ),
        examples=["eu_west"],
    )


class FieldValueView(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    data_type: str
    value: Any
    field_version: int = Field(description="The field version the value was set under.")
    is_field_archived: bool
    set_by_user_id: uuid.UUID
    set_at: datetime
