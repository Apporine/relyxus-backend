"""Team role grants (Q-18, ADR-0003 §6; MPS-14.01 "permissions follow team and workspace").

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-15

`team_role_grants` holds workspace roles a team's members inherit. Access is resolved
before any tenant is chosen, under the user context only, so reads widen like
workspace_memberships (migration 0003):
- team_members: your tenant, or your own memberships;
- team_role_grants: your tenant, or grants of a team you belong to.
Writes still require the tenant context (WITH CHECK unchanged).

Rollout: expand only (new table, read policy widened to the user's own rows). Rollback
plan: downgrade drops the table and restores the 0024 team_members policy.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT = "organization_id = relyxus_current_organization_id()"
_OWN_MEMBERSHIP = "user_id = relyxus_current_user_id()"
_MEMBER_OF_TEAM = (
    "EXISTS (SELECT 1 FROM team_members m"
    " WHERE m.team_id = team_role_grants.team_id AND m.user_id = relyxus_current_user_id())"
)
_ROLES_SQL = (
    "'owner', 'admin', 'security_admin', 'compliance_officer', 'policy_owner', "
    "'incident_commander', 'responder', 'viewer', 'auditor'"
)


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def _set_policy(table: str, extra_visibility: str | None) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    visibility = _TENANT if extra_visibility is None else f"{_TENANT} OR {extra_visibility}"
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table}"
        f" USING ({visibility}) WITH CHECK ({_TENANT})"
    )


def upgrade() -> None:
    op.create_table(
        "team_role_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_team_role_grants"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_team_role_grants_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["team_id", "workspace_id"],
            ["teams.id", "teams.workspace_id"],
            name="fk_team_role_grants_team_same_workspace",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("team_id", "role", name="uq_team_role_grants_team_id_role"),
        sa.CheckConstraint(f"role IN ({_ROLES_SQL})", name="ck_team_role_grants_role"),
    )
    for column in ("organization_id", "workspace_id"):
        op.create_index(f"ix_team_role_grants_{column}", "team_role_grants", [column])
    op.execute("ALTER TABLE team_role_grants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE team_role_grants FORCE ROW LEVEL SECURITY")
    _set_policy("team_role_grants", _MEMBER_OF_TEAM)
    _set_policy("team_members", _OWN_MEMBERSHIP)


def downgrade() -> None:
    _set_policy("team_members", None)
    op.drop_table("team_role_grants")
