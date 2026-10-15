import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from relyxus_api.modules.incident.timeline_model import IncidentTimelineEvent

NOTE_TEXT_MAX_LENGTH = 4000


class AddNoteRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NOTE_TEXT_MAX_LENGTH)
    ] = Field(examples=["Provider confirms elevated card declines in eu-west-1."])


class TimelineEventView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    kind: str = Field(
        description="What happened, such as `incident.transitioned` or `incident.task_created`.",
        examples=["incident.transitioned"],
    )
    actor_user_id: uuid.UUID | None = Field(description="Who did it; null for system events.")
    subject_type: str = Field(
        description="What changed: `incident`, `incident_task` or `incident_note`.",
        examples=["incident"],
    )
    subject_id: uuid.UUID
    before: dict[str, Any] | None = Field(description="The changed fields before the change.")
    after: dict[str, Any] | None = Field(description="The changed fields after the change.")
    occurred_at: datetime

    @classmethod
    def from_event(cls, event: IncidentTimelineEvent) -> "TimelineEventView":
        return cls(
            id=event.id,
            incident_id=event.incident_id,
            kind=event.kind,
            actor_user_id=event.actor_user_id,
            subject_type=event.subject_type,
            subject_id=event.subject_id,
            before=event.before_state,
            after=event.after_state,
            occurred_at=event.created_at,
        )
