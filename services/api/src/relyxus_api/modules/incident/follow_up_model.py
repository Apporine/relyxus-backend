"""Post-incident follow-ups: actions that outlive the incident (MPS-26.02, MPS-13.17).

Distinct from live tasks (MPS-11.14): tasks are work during the incident, follow-ups are
work after it. Mandatory follow-ups need an owner and a due date before a SEV1 or SEV2
incident can close (MPS-13.17).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.modules.incident.task_model import CANCELLATION_REASON_MAX_LENGTH
from relyxus_api.shared.db.base import Base, RecordColumns

FOLLOW_UP_TITLE_MAX_LENGTH = 500


class FollowUpStatus(StrEnum):
    """Done and cancelled are final, as for tasks (register Q-36)."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


FINAL_FOLLOW_UP_STATUSES = frozenset({FollowUpStatus.DONE, FollowUpStatus.CANCELLED})


class FollowUpSource(StrEnum):
    MANUAL = "manual"
    LIVE_TASK = "live_task"


def _values_sql(values: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in values)


class IncidentFollowUp(RecordColumns, Base):
    __tablename__ = "incident_follow_ups"
    __table_args__ = (
        ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_follow_ups_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        CheckConstraint("char_length(title) >= 1", name="title_length"),
        CheckConstraint(f"status IN ({_values_sql(FollowUpStatus)})", name="status"),
        CheckConstraint(f"source IN ({_values_sql(FollowUpSource)})", name="source"),
        CheckConstraint(
            "(source = 'live_task') = (source_task_id IS NOT NULL)", name="source_task_matches"
        ),
        CheckConstraint(
            "(status = 'cancelled') = (cancellation_reason IS NOT NULL)",
            name="cancelled_has_reason",
        ),
        CheckConstraint(
            "(status = 'done') = (completed_at IS NOT NULL)", name="done_has_completion"
        ),
        Index("ix_incident_follow_ups_incident_id_id", "incident_id", "id"),
        Index("ix_incident_follow_ups_organization_id", "organization_id"),
        Index("ix_incident_follow_ups_workspace_id", "workspace_id"),
        Index("ix_incident_follow_ups_owner_user_id", "owner_user_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    incident_id: Mapped[uuid.UUID]
    title: Mapped[str] = mapped_column(String(FOLLOW_UP_TITLE_MAX_LENGTH))
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    due_at: Mapped[datetime | None]
    is_mandatory: Mapped[bool]
    status: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    source_task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incident_tasks.id", ondelete="RESTRICT"), unique=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(CANCELLATION_REASON_MAX_LENGTH))
    completed_at: Mapped[datetime | None]
    completed_by_user_id: Mapped[uuid.UUID | None]
    created_by_user_id: Mapped[uuid.UUID]
