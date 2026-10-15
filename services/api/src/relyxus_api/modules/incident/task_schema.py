import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from relyxus_api.modules.incident.task_model import (
    CANCELLATION_REASON_MAX_LENGTH,
    TASK_TITLE_MAX_LENGTH,
    IncidentTask,
    TaskPriority,
    TaskSource,
    TaskStatus,
)

TaskTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TASK_TITLE_MAX_LENGTH)
]
TaskReason = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=CANCELLATION_REASON_MAX_LENGTH
    ),
]


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: TaskTitle = Field(examples=["Confirm provider status with the card processor"])
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, examples=[TaskPriority.HIGH])
    owner_user_id: uuid.UUID | None = Field(
        default=None, description="One owner; omit to leave the task unassigned."
    )
    due_at: AwareDatetime | None = Field(default=None, examples=["2026-10-15T09:30:00Z"])


class UpdateTaskRequest(BaseModel):
    """Partial update. Send `owner_user_id` or `due_at` as null to clear them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: TaskTitle | None = None
    priority: TaskPriority | None = None
    owner_user_id: uuid.UUID | None = None
    due_at: AwareDatetime | None = None
    status: TaskStatus | None = Field(default=None, examples=[TaskStatus.IN_PROGRESS])
    reason: TaskReason | None = Field(
        default=None, description="Required when cancelling.", examples=["No longer needed"]
    )


class TaskView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    title: str
    priority: TaskPriority
    status: TaskStatus
    owner_user_id: uuid.UUID | None
    is_unassigned: bool = Field(description="True when nobody owns the task (MPS-11.14).")
    due_at: datetime | None
    source: TaskSource
    cancellation_reason: str | None
    completed_at: datetime | None
    completed_by_user_id: uuid.UUID | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_task(cls, task: IncidentTask) -> "TaskView":
        return cls(
            id=task.id,
            incident_id=task.incident_id,
            title=task.title,
            priority=TaskPriority(task.priority),
            status=TaskStatus(task.status),
            owner_user_id=task.owner_user_id,
            is_unassigned=task.owner_user_id is None,
            due_at=task.due_at,
            source=TaskSource(task.source),
            cancellation_reason=task.cancellation_reason,
            completed_at=task.completed_at,
            completed_by_user_id=task.completed_by_user_id,
            created_by_user_id=task.created_by_user_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
