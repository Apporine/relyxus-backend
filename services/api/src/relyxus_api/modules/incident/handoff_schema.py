import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from relyxus_api.modules.incident.handoff_model import HandoffState, IncidentRoleHandoff
from relyxus_api.modules.incident.role_model import IncidentRole


class RequestHandoffRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role: IncidentRole = Field(examples=[IncidentRole.INCIDENT_COMMANDER])
    to_user_id: uuid.UUID = Field(examples=["0192f0c4-0000-7000-8000-0000000000f2"])


class HandoffView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    role: IncidentRole
    state: HandoffState
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID
    requested_by_user_id: uuid.UUID
    package: dict[str, Any] = Field(
        description=(
            "What the incoming person is handed, captured when the handoff was requested: "
            "incident summary, role holders and unfinished tasks. Sections Relyxus cannot "
            "fill yet are named in `unavailable_sections`."
        )
    )
    requested_at: datetime
    accepted_at: datetime | None
    cancelled_at: datetime | None
    cancelled_by_user_id: uuid.UUID | None

    @classmethod
    def from_handoff(cls, handoff: IncidentRoleHandoff) -> "HandoffView":
        return cls(
            id=handoff.id,
            incident_id=handoff.incident_id,
            role=IncidentRole(handoff.role),
            state=HandoffState(handoff.state),
            from_user_id=handoff.from_user_id,
            to_user_id=handoff.to_user_id,
            requested_by_user_id=handoff.requested_by_user_id,
            package=handoff.package_snapshot,
            requested_at=handoff.created_at,
            accepted_at=handoff.accepted_at,
            cancelled_at=handoff.cancelled_at,
            cancelled_by_user_id=handoff.cancelled_by_user_id,
        )
