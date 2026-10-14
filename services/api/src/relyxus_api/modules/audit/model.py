"""Append-only, hash-chained audit events (MPS-14.16, MPS-20.25, MPS-28.23; ADR-0003 §6).

One chain per workspace, plus one organisation-level chain (`workspace_id` NULL) for
records that belong to no workspace. `chain_id` is that workspace or organisation ID.
Rows are never updated or deleted: database triggers reject both (migration 0005).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns

HASH_HEX_LENGTH = 64


class ActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    SUPPORT = "support"


class AuditOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    DENIED = "denied"
    FAILED = "failed"


class AuditEvent(RecordColumns, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("chain_id", "sequence", name="uq_audit_events_chain_id_sequence"),
        CheckConstraint("sequence >= 1", name="sequence_positive"),
        CheckConstraint("actor_type IN ('user', 'system', 'support')", name="actor_type"),
        CheckConstraint("outcome IN ('succeeded', 'denied', 'failed')", name="outcome"),
        Index("ix_audit_events_organization_id_occurred_at", "organization_id", "occurred_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    chain_id: Mapped[uuid.UUID]
    sequence: Mapped[int] = mapped_column(BigInteger)
    occurred_at: Mapped[datetime]
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_user_id: Mapped[uuid.UUID | None]
    # Who the action was performed as, when it differs from the actor (delegation,
    # break-glass, support sessions; MPS-28.23 "effective identity").
    effective_user_id: Mapped[uuid.UUID | None]
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(128))
    outcome: Mapped[str] = mapped_column(String(16))
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    correlation_id: Mapped[str] = mapped_column(String(128))
    previous_hash: Mapped[str | None] = mapped_column(String(HASH_HEX_LENGTH))
    entry_hash: Mapped[str] = mapped_column(String(HASH_HEX_LENGTH))
