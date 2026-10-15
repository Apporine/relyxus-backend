"""Who holds each incident role right now (MPS-11.04). History is in the audit chain."""

import uuid
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

from relyxus_api.shared.db.base import Base, RecordColumns


class IncidentRole(StrEnum):
    """MPS-11.04 incident roles; distinct from workspace roles (MPS-14)."""

    INCIDENT_COMMANDER = "incident_commander"
    COMMUNICATIONS_LEAD = "communications_lead"
    SCRIBE = "scribe"


_ROLES_SQL = ", ".join(f"'{role.value}'" for role in IncidentRole)


class IncidentRoleAssignment(RecordColumns, Base):
    __tablename__ = "incident_role_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_role_assignments_incident_same_workspace",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "incident_id", "role", name="uq_incident_role_assignments_incident_id_role"
        ),
        CheckConstraint(f"role IN ({_ROLES_SQL})", name="role"),
        Index("ix_incident_role_assignments_organization_id", "organization_id"),
        Index("ix_incident_role_assignments_workspace_id", "workspace_id"),
        Index("ix_incident_role_assignments_user_id", "user_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    incident_id: Mapped[uuid.UUID]
    role: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assigned_by_user_id: Mapped[uuid.UUID]
