"""Teams and team members (MPS-14.01, MPS-20.05).

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-15

Teams belong to a workspace (composite FK to workspaces(id, organization_id)); keys are
unique per workspace. Members reference teams(id, workspace_id), so a membership can
never cross workspaces. Both tables use forced RLS by organisation.

Rollout: expand only (new tables). Rollback plan: the previous release does not read them.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table}"
        " USING (organization_id = relyxus_current_organization_id())"
        " WITH CHECK (organization_id = relyxus_current_organization_id())"
    )


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(63), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_teams"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_teams_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_teams_workspace_organization",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("workspace_id", "key", name="uq_teams_workspace_id_key"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_teams_id_workspace_id"),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9-]{1,62}$'", name="ck_teams_key_format"),
        sa.CheckConstraint("char_length(name) >= 1", name="ck_teams_name_length"),
    )
    op.create_index("ix_teams_organization_id", "teams", ["organization_id"])
    op.create_table(
        "team_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("added_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_team_members"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_team_members_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["team_id", "workspace_id"],
            ["teams.id", "teams.workspace_id"],
            name="fk_team_members_team_same_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_team_members_user_id_users", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_members_team_id_user_id"),
    )
    for column in ("organization_id", "workspace_id", "user_id"):
        op.create_index(f"ix_team_members_{column}", "team_members", [column])
    for table in ("teams", "team_members"):
        _enable_rls(table)


def downgrade() -> None:
    op.drop_table("team_members")
    op.drop_table("teams")
