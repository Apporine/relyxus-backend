"""Teams inside a workspace and their members (MPS-14.01, MPS-20.05).

A user can be in several teams. Teams own services (MPS-20.08) and carry workspace role
grants that their members inherit (Q-18, ADR-0003 §6): a member's roles are their direct
grants plus their teams' grants. On-call schedules (MPS-20.05) come later.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.shared.db.base import Base, RecordColumns

TEAM_NAME_MAX_LENGTH = 200
TEAM_DESCRIPTION_MAX_LENGTH = 2000
TEAM_KEY_MAX_LENGTH = 63
TEAM_KEY_PATTERN = "^[a-z][a-z0-9-]{1,62}$"


class Team(RecordColumns, Base):
    __tablename__ = "teams"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_teams_workspace_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("workspace_id", "key", name="uq_teams_workspace_id_key"),
        # Target for composite foreign keys, so members stay in the team's workspace.
        UniqueConstraint("id", "workspace_id", name="uq_teams_id_workspace_id"),
        CheckConstraint(f"key ~ '{TEAM_KEY_PATTERN}'", name="key_format"),
        CheckConstraint("char_length(name) >= 1", name="name_length"),
        Index("ix_teams_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    key: Mapped[str] = mapped_column(String(TEAM_KEY_MAX_LENGTH))
    name: Mapped[str] = mapped_column(String(TEAM_NAME_MAX_LENGTH))
    description: Mapped[str | None] = mapped_column(String(TEAM_DESCRIPTION_MAX_LENGTH))


class TeamMember(RecordColumns, Base):
    __tablename__ = "team_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "workspace_id"],
            ["teams.id", "teams.workspace_id"],
            name="fk_team_members_team_same_workspace",
            ondelete="CASCADE",
        ),
        UniqueConstraint("team_id", "user_id", name="uq_team_members_team_id_user_id"),
        Index("ix_team_members_organization_id", "organization_id"),
        Index("ix_team_members_workspace_id", "workspace_id"),
        Index("ix_team_members_user_id", "user_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    team_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    added_by_user_id: Mapped[uuid.UUID]


_ROLES_SQL = ", ".join(f"'{role.value}'" for role in WorkspaceRole)


class TeamRoleGrant(RecordColumns, Base):
    """A workspace role every member of the team holds in the team's workspace."""

    __tablename__ = "team_role_grants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "workspace_id"],
            ["teams.id", "teams.workspace_id"],
            name="fk_team_role_grants_team_same_workspace",
            ondelete="CASCADE",
        ),
        UniqueConstraint("team_id", "role", name="uq_team_role_grants_team_id_role"),
        CheckConstraint(f"role IN ({_ROLES_SQL})", name="role"),
        Index("ix_team_role_grants_organization_id", "organization_id"),
        Index("ix_team_role_grants_workspace_id", "workspace_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    team_id: Mapped[uuid.UUID]
    role: Mapped[str] = mapped_column(String(32))
    granted_by_user_id: Mapped[uuid.UUID]
