"""Incident visibility modes and access grants (MPS-8A.23, MPS-20.30).

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-15

Adds `incidents.visibility` (default `workspace`, so existing incidents keep today's
behaviour) and `incidents.created_by_user_id` (NULL for existing rows), and the
`incident_access_grants` table: exactly one of person, team or role per grant, with a
reason and optional expiry; composite FKs keep incident and team in the grant's
workspace. Forced RLS by organisation.

Visibility is enforced in the application's incident repository today (one predicate on
every incident read). Database-level (RLS) enforcement is a planned defence in depth.

Rollout: expand only; the default keeps every existing incident workspace-visible.
Rollback plan: the previous release ignores the new column and table; restricted
incidents would then become visible to their whole workspace again.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VISIBILITY_CHECK = "ck_incidents_visibility"
_ROLES_SQL = (
    "'owner', 'admin', 'security_admin', 'compliance_officer', 'policy_owner', "
    "'incident_commander', 'responder', 'viewer', 'auditor'"
)


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("visibility", sa.String(16), server_default="workspace", nullable=False),
    )
    op.add_column("incidents", sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
    op.create_check_constraint(
        _VISIBILITY_CHECK,
        "incidents",
        "visibility IN ('workspace', 'restricted', 'invite_only', 'confidential')",
    )
    op.create_table(
        "incident_access_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(32), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_incident_access_grants"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_incident_access_grants_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_access_grants_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["team_id", "workspace_id"],
            ["teams.id", "teams.workspace_id"],
            name="fk_incident_access_grants_team_same_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_incident_access_grants_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "num_nonnulls(user_id, team_id, role) = 1",
            name="ck_incident_access_grants_exactly_one_grantee",
        ),
        sa.CheckConstraint(
            f"role IS NULL OR role IN ({_ROLES_SQL})", name="ck_incident_access_grants_role"
        ),
        sa.CheckConstraint(
            "char_length(reason) >= 1", name="ck_incident_access_grants_reason_length"
        ),
    )
    for column in ("incident_id", "organization_id", "workspace_id"):
        op.create_index(f"ix_incident_access_grants_{column}", "incident_access_grants", [column])
    op.execute("ALTER TABLE incident_access_grants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE incident_access_grants FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY incident_access_grants_tenant_isolation ON incident_access_grants"
        " USING (organization_id = relyxus_current_organization_id())"
        " WITH CHECK (organization_id = relyxus_current_organization_id())"
    )


def downgrade() -> None:
    op.drop_table("incident_access_grants")
    op.drop_constraint(_VISIBILITY_CHECK, "incidents", type_="check")
    op.drop_column("incidents", "created_by_user_id")
    op.drop_column("incidents", "visibility")
