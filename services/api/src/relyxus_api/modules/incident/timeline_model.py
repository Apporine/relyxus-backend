"""The incident timeline: what happened to an incident, in order (MPS-5.20, MPS-8A.33, MPS-11.20).

Product-facing, unlike the audit chain (a security record that only auditors read). Every
incident change writes one timeline event in the same transaction as its audit entry.
Rows are never updated or deleted: database triggers reject both (migration 0016).
`sequence` gives a strict order even when several events share a millisecond.
"""

import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns


class IncidentTimelineEvent(RecordColumns, Base):
    __tablename__ = "incident_timeline_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_timeline_events_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("sequence", name="uq_incident_timeline_events_sequence"),
        Index("ix_incident_timeline_events_incident_id_sequence", "incident_id", "sequence"),
        Index("ix_incident_timeline_events_organization_id", "organization_id"),
        Index("ix_incident_timeline_events_workspace_id", "workspace_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    incident_id: Mapped[uuid.UUID]
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(always=True))
    kind: Mapped[str] = mapped_column(String(100))
    actor_user_id: Mapped[uuid.UUID | None]
    subject_type: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[uuid.UUID]
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
