"""Users and workspace role grants (MPS-14.01-14.09, MPS-20.04, MPS-20.06; ADR-0003 §6).

A user is a login identity (issuer + subject), which MPS-17.17 allows to be global. Access
comes only from workspace memberships, one row per role held in a workspace. Team grants
(Q-18) will be added alongside teams.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns

IDENTITY_MAX_LENGTH = 255
EMAIL_MAX_LENGTH = 320
DISPLAY_NAME_MAX_LENGTH = 200


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPROVISIONED = "deprovisioned"


class WorkspaceRole(StrEnum):
    """The nine built-in roles (MPS-14.02-14.09, single definitions MPS-26.02)."""

    OWNER = "owner"
    ADMIN = "admin"
    SECURITY_ADMIN = "security_admin"
    COMPLIANCE_OFFICER = "compliance_officer"
    POLICY_OWNER = "policy_owner"
    INCIDENT_COMMANDER = "incident_commander"
    RESPONDER = "responder"
    VIEWER = "viewer"
    AUDITOR = "auditor"


def _values_sql(values: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in values)


class User(RecordColumns, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("idp_issuer", "idp_subject", name="uq_users_idp_issuer_idp_subject"),
        CheckConstraint(f"status IN ({_values_sql(UserStatus)})", name="status"),
    )

    idp_issuer: Mapped[str] = mapped_column(String(IDENTITY_MAX_LENGTH))
    idp_subject: Mapped[str] = mapped_column(String(IDENTITY_MAX_LENGTH))
    email: Mapped[str | None] = mapped_column(String(EMAIL_MAX_LENGTH))
    display_name: Mapped[str | None] = mapped_column(String(DISPLAY_NAME_MAX_LENGTH))
    status: Mapped[str] = mapped_column(String(20))
    last_signed_in_at: Mapped[datetime | None]


class WorkspaceMembership(RecordColumns, Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_workspace_memberships_workspace_organization",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "workspace_id", "user_id", "role", name="uq_workspace_memberships_workspace_user_role"
        ),
        CheckConstraint(f"role IN ({_values_sql(WorkspaceRole)})", name="role"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))
