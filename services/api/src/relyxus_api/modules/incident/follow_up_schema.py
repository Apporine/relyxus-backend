import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from relyxus_api.modules.incident.follow_up_model import (
    FOLLOW_UP_TITLE_MAX_LENGTH,
    FollowUpSource,
    FollowUpStatus,
    IncidentFollowUp,
)
from relyxus_api.modules.incident.task_schema import TaskReason

FollowUpTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=FOLLOW_UP_TITLE_MAX_LENGTH),
]


class CreateFollowUpRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: FollowUpTitle = Field(examples=["Add alerting on card-processor error rate"])
    owner_user_id: uuid.UUID | None = Field(default=None)
    due_at: AwareDatetime | None = Field(default=None, examples=["2026-11-01T17:00:00Z"])
    is_mandatory: bool | None = Field(
        default=None,
        description=(
            "Mandatory follow-ups gate closing SEV1/SEV2 incidents (MPS-13.17). Defaults to "
            "true for SEV1 and SEV2, false otherwise."
        ),
    )


class UpdateFollowUpRequest(BaseModel):
    """Partial update. Send `owner_user_id` or `due_at` as null to clear them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: FollowUpTitle | None = None
    owner_user_id: uuid.UUID | None = None
    due_at: AwareDatetime | None = None
    is_mandatory: bool | None = None
    status: FollowUpStatus | None = Field(default=None, examples=[FollowUpStatus.IN_PROGRESS])
    reason: TaskReason | None = Field(default=None, description="Required when cancelling.")


class FollowUpView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    title: str
    owner_user_id: uuid.UUID | None
    due_at: datetime | None
    is_mandatory: bool
    status: FollowUpStatus
    source: FollowUpSource
    source_task_id: uuid.UUID | None = Field(
        description="The live task this follow-up was created from, if any."
    )
    cancellation_reason: str | None
    completed_at: datetime | None
    completed_by_user_id: uuid.UUID | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_follow_up(cls, follow_up: IncidentFollowUp) -> "FollowUpView":
        return cls(
            id=follow_up.id,
            incident_id=follow_up.incident_id,
            title=follow_up.title,
            owner_user_id=follow_up.owner_user_id,
            due_at=follow_up.due_at,
            is_mandatory=follow_up.is_mandatory,
            status=FollowUpStatus(follow_up.status),
            source=FollowUpSource(follow_up.source),
            source_task_id=follow_up.source_task_id,
            cancellation_reason=follow_up.cancellation_reason,
            completed_at=follow_up.completed_at,
            completed_by_user_id=follow_up.completed_by_user_id,
            created_by_user_id=follow_up.created_by_user_id,
            created_at=follow_up.created_at,
            updated_at=follow_up.updated_at,
        )
