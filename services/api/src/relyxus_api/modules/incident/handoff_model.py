"""Incident role handoffs (MPS-11.23, MPS-11.24, MPS-20.33).

A handoff moves one incident role from its current holder to another member. It stays
pending until the incoming person accepts it; only then does the role change. The package
snapshot records what the incoming person was shown.

Not yet: deferred items. MPS-11.24 asks for approvals and clocks due within an hour to be
acknowledged or deferred with a reason; neither approvals nor clocks exist yet, so the
column arrives with them.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.modules.incident.role_model import IncidentRole
from relyxus_api.shared.db.base import Base, RecordColumns


class HandoffState(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    CANCELLED = "cancelled"


def _values_sql(values: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in values)


class IncidentRoleHandoff(RecordColumns, Base):
    __tablename__ = "incident_role_handoffs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_role_handoffs_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        CheckConstraint(f"role IN ({_values_sql(IncidentRole)})", name="role"),
        CheckConstraint(f"state IN ({_values_sql(HandoffState)})", name="state"),
        CheckConstraint("from_user_id <> to_user_id", name="different_people"),
        CheckConstraint(
            "(state = 'accepted') = (accepted_at IS NOT NULL)", name="accepted_has_time"
        ),
        CheckConstraint(
            "(state = 'cancelled') = (cancelled_at IS NOT NULL)", name="cancelled_has_time"
        ),
        # At most one open handoff per role of an incident.
        Index(
            "uq_incident_role_handoffs_pending_role",
            "incident_id",
            "role",
            unique=True,
            postgresql_where=text("state = 'pending'"),
        ),
        Index("ix_incident_role_handoffs_incident_id_id", "incident_id", "id"),
        Index("ix_incident_role_handoffs_organization_id", "organization_id"),
        Index("ix_incident_role_handoffs_workspace_id", "workspace_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    incident_id: Mapped[uuid.UUID]
    role: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(16))
    from_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    requested_by_user_id: Mapped[uuid.UUID]
    package_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    accepted_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    cancelled_by_user_id: Mapped[uuid.UUID | None]
