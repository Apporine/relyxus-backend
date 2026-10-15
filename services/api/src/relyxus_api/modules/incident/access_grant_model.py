"""Who may see a non-workspace incident (MPS-8A.23, MPS-20.30 Incident Visibility Grant).

A grant names exactly one person, team or workspace role, with a reason and an optional
expiry. Team and role grants count only for `restricted` incidents; `invite_only` and
`confidential` incidents honour person grants only.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.shared.db.base import Base, RecordColumns

GRANT_REASON_MAX_LENGTH = 1000
MAX_ACCESS_GRANTS = 200

_ROLES_SQL = ", ".join(f"'{role.value}'" for role in WorkspaceRole)


class IncidentAccessGrant(RecordColumns, Base):
    __tablename__ = "incident_access_grants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_access_grants_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["team_id", "workspace_id"],
            ["teams.id", "teams.workspace_id"],
            name="fk_incident_access_grants_team_same_workspace",
            ondelete="CASCADE",
        ),
        CheckConstraint("num_nonnulls(user_id, team_id, role) = 1", name="exactly_one_grantee"),
        CheckConstraint(f"role IS NULL OR role IN ({_ROLES_SQL})", name="role"),
        CheckConstraint("char_length(reason) >= 1", name="reason_length"),
        Index("ix_incident_access_grants_incident_id", "incident_id"),
        Index("ix_incident_access_grants_organization_id", "organization_id"),
        Index("ix_incident_access_grants_workspace_id", "workspace_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    incident_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    team_id: Mapped[uuid.UUID | None]
    role: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(GRANT_REASON_MAX_LENGTH))
    expires_at: Mapped[datetime | None]
    granted_by_user_id: Mapped[uuid.UUID]
