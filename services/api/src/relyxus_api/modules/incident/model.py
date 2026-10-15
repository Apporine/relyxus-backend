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
ROOT_CAUSE_MAX_LENGTH = 5000


class IncidentVisibility(StrEnum):
    """MPS-8A.23 visibility modes (Ph0 model)."""

    WORKSPACE = "workspace"  # everyone with workspace access
    RESTRICTED = "restricted"  # named people, teams or roles
    INVITE_ONLY = "invite_only"  # named people only
    CONFIDENTIAL = "confidential"  # invite only; export lock and retention hold to come


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
        CheckConstraint(f"visibility IN ({_values_sql(IncidentVisibility)})", name="visibility"),
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
        UniqueConstraint("workspace_id", "number", name="uq_incidents_workspace_id_number"),
        CheckConstraint("number >= 1", name="number_positive"),
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
        CheckConstraint(
            "impact_started_at IS NULL OR detected_at IS NULL OR impact_started_at <= detected_at",
            name="impact_not_after_detection",
        ),
        CheckConstraint(
            "(acknowledged_at IS NULL) = (acknowledged_by_user_id IS NULL)",
            name="acknowledged_has_actor",
        ),
        CheckConstraint(
            "lifecycle_state <> 'closed' OR closed_at IS NOT NULL", name="closed_has_time"
        ),
        ForeignKeyConstraint(
            ["incident_type_id", "workspace_id"],
            ["incident_types.id", "incident_types.workspace_id"],
            name="fk_incidents_incident_type_same_workspace",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(incident_type_id IS NULL) = (incident_type_version IS NULL)",
            name="type_has_version",
        ),
        Index("ix_incidents_incident_type_id", "incident_type_id"),
        Index("ix_incidents_merged_into_incident_id", "merged_into_incident_id"),
        Index("ix_incidents_workspace_id_lifecycle_state", "workspace_id", "lifecycle_state"),
        Index("ix_incidents_organization_id", "organization_id"),
        Index("ix_incidents_workspace_id_id", "workspace_id", "id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column()
    # Per-workspace display number (MPS-20.12), e.g. shown as INC-42. Never an identifier.
    number: Mapped[int]
    lifecycle_state: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    visibility: Mapped[str] = mapped_column(
        String(16), default=IncidentVisibility.WORKSPACE.value, server_default="workspace"
    )
    # The type and its configuration version at declaration (MPS-8A.06, MPS-20.12).
    incident_type_id: Mapped[uuid.UUID | None]
    incident_type_version: Mapped[int | None]
    # Who created the record (declared or drafted); NULL for rows created before 0028.
    created_by_user_id: Mapped[uuid.UUID | None]
    # Reported by people (or, later, alerts): when impact began and when it was noticed.
    impact_started_at: Mapped[datetime | None]
    detected_at: Mapped[datetime | None]
    # First acknowledgement by a responder (MPS-15.02 war room "Acknowledge").
    acknowledged_at: Mapped[datetime | None]
    acknowledged_by_user_id: Mapped[uuid.UUID | None]
    # The "declared" metric timestamp (MPS-8A.20); set when the incident leaves triage.
    declared_at: Mapped[datetime | None]
    declared_by_user_id: Mapped[uuid.UUID | None]
    # Remaining MPS-8A.20 metric timestamps, set by lifecycle transitions.
    mitigated_at: Mapped[datetime | None]
    resolved_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    closed_by_user_id: Mapped[uuid.UUID | None]
    # MPS-13.04 root cause captured at closing; MPS-13.17 authorised closure exception.
    root_cause: Mapped[str | None] = mapped_column(String(ROOT_CAUSE_MAX_LENGTH))
    closure_exception_reason: Mapped[str | None] = mapped_column(String(1000))
    cancelled_at: Mapped[datetime | None]
    merged_into_incident_id: Mapped[uuid.UUID | None]
