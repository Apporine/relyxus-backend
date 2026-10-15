"""Workspace-scoped incident records (MPS-8A.07, MPS-8A.08, MPS-8A.20)."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.shared.db.base import Base, RecordColumns

TITLE_MAX_LENGTH = 500


class IncidentSeverity(StrEnum):
    """Default four-level guide (MPS-8.13); types may restrict subsets in Ph1."""

    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"


def _values_sql(values: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in values)


class Incident(RecordColumns, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_incidents_workspace_organization",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"lifecycle_state IN ({_values_sql(IncidentLifecycleState)})",
            name="lifecycle_state",
        ),
        CheckConstraint(f"severity IN ({_values_sql(IncidentSeverity)})", name="severity"),
        CheckConstraint(
            f"char_length(title) >= 1 AND char_length(title) <= {TITLE_MAX_LENGTH}",
            name="title_length",
        ),
        CheckConstraint(
            "lifecycle_state = 'triage' OR declared_at IS NOT NULL",
            name="declared_when_past_triage",
        ),
        # Target of the composite merge foreign key below.
        UniqueConstraint("id", "workspace_id", name="uq_incidents_id_workspace_id"),
        ForeignKeyConstraint(
            ["merged_into_incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incidents_merged_into_same_workspace",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(lifecycle_state = 'merged') = (merged_into_incident_id IS NOT NULL)",
            name="merged_has_target",
        ),
        CheckConstraint("merged_into_incident_id IS DISTINCT FROM id", name="not_merged_into_self"),
        Index("ix_incidents_merged_into_incident_id", "merged_into_incident_id"),
        Index("ix_incidents_workspace_id_lifecycle_state", "workspace_id", "lifecycle_state"),
        Index("ix_incidents_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column()
    lifecycle_state: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    # The "declared" metric timestamp (MPS-8A.20); set when the incident leaves triage.
    declared_at: Mapped[datetime | None]
    declared_by_user_id: Mapped[uuid.UUID | None]
    # Remaining MPS-8A.20 metric timestamps, set by lifecycle transitions.
    mitigated_at: Mapped[datetime | None]
    resolved_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    merged_into_incident_id: Mapped[uuid.UUID | None]
