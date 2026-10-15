"""Live incident tasks: parallel work during an incident (MPS-11.14-11.22, MPS-20.32).

Distinct from post-incident follow-ups (MPS-26.02). Visibility follows the incident.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns

TASK_TITLE_MAX_LENGTH = 500
CANCELLATION_REASON_MAX_LENGTH = 1000


class TaskPriority(StrEnum):
    """Provisional scale: MPS-11.14 names a priority but defines no values (register Q-35)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(StrEnum):
    """MPS-11.15. Done and cancelled are final until register Q-36 says otherwise."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


FINAL_TASK_STATUSES = frozenset({TaskStatus.DONE, TaskStatus.CANCELLED})


class TaskSource(StrEnum):
    """MPS-11.19 also lists template, playbook, workflow and AI suggestion; added with them."""

    MANUAL = "manual"


def _values_sql(values: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in values)


class IncidentTask(RecordColumns, Base):
    __tablename__ = "incident_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_tasks_incident_same_workspace",
            ondelete="CASCADE",
        ),
        CheckConstraint("char_length(title) >= 1", name="title_length"),
        CheckConstraint(f"priority IN ({_values_sql(TaskPriority)})", name="priority"),
        CheckConstraint(f"status IN ({_values_sql(TaskStatus)})", name="status"),
        CheckConstraint(f"source IN ({_values_sql(TaskSource)})", name="source"),
        CheckConstraint(
            "(status = 'cancelled') = (cancellation_reason IS NOT NULL)",
            name="cancelled_has_reason",
        ),
        CheckConstraint(
            "(status = 'done') = (completed_at IS NOT NULL)", name="done_has_completion"
        ),
        Index("ix_incident_tasks_incident_id_id", "incident_id", "id"),
        Index("ix_incident_tasks_organization_id", "organization_id"),
        Index("ix_incident_tasks_workspace_id", "workspace_id"),
        Index("ix_incident_tasks_owner_user_id", "owner_user_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    incident_id: Mapped[uuid.UUID]
    title: Mapped[str] = mapped_column(String(TASK_TITLE_MAX_LENGTH))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    priority: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    due_at: Mapped[datetime | None]
    source: Mapped[str] = mapped_column(String(32))
    cancellation_reason: Mapped[str | None] = mapped_column(String(CANCELLATION_REASON_MAX_LENGTH))
    completed_at: Mapped[datetime | None]
    completed_by_user_id: Mapped[uuid.UUID | None]
    created_by_user_id: Mapped[uuid.UUID]
