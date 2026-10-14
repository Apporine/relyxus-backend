"""Users and workspace memberships with row-level security.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14

Rollout: expand only (new tables and functions); safe with the previous release.
Rollback plan: the previous release does not read these tables, so it runs unchanged.

Visibility rules:
- A user row is visible to its own identity (issuer + subject), by user ID once resolved,
  or to an organisation the user belongs to. Identity lookup must work before any tenant
  is known.
- A membership row is visible within its organisation or to the user it belongs to, so a
  caller can find their own grants before a tenant is chosen. Writes need org context.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SETTING_FUNCTIONS = {
    "relyxus_current_user_id": ("app.user_id", "uuid"),
    "relyxus_current_idp_issuer": ("app.idp_issuer", "text"),
    "relyxus_current_idp_subject": ("app.idp_subject", "text"),
}
_ROLES = (
    "owner",
    "admin",
    "security_admin",
    "compliance_officer",
    "policy_owner",
    "incident_commander",
    "responder",
    "viewer",
    "auditor",
)

_USERS_POLICY = """
CREATE POLICY users_visibility ON users
USING (
    (idp_issuer = relyxus_current_idp_issuer() AND idp_subject = relyxus_current_idp_subject())
    OR id = relyxus_current_user_id()
    OR EXISTS (
        SELECT 1 FROM workspace_memberships m
        WHERE m.user_id = users.id AND m.organization_id = relyxus_current_organization_id()
    )
)
WITH CHECK (id = relyxus_current_user_id())
"""

_MEMBERSHIPS_POLICY = """
CREATE POLICY workspace_memberships_visibility ON workspace_memberships
USING (
    organization_id = relyxus_current_organization_id()
    OR user_id = relyxus_current_user_id()
)
WITH CHECK (organization_id = relyxus_current_organization_id())
"""


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    for function, (setting, sql_type) in _SETTING_FUNCTIONS.items():
        op.execute(
            f"CREATE FUNCTION {function}() RETURNS {sql_type} LANGUAGE sql STABLE AS "
            f"$$ SELECT NULLIF(current_setting('{setting}', true), '')::{sql_type} $$"
        )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idp_issuer", sa.String(255), nullable=False),
        sa.Column("idp_subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_signed_in_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("idp_issuer", "idp_subject", name="uq_users_idp_issuer_idp_subject"),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'deprovisioned')", name="ck_users_status"
        ),
    )
    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_memberships"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_workspace_memberships_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_workspace_memberships_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_workspace_memberships_workspace_organization",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "workspace_id", "user_id", "role", name="uq_workspace_memberships_workspace_user_role"
        ),
        sa.CheckConstraint(
            "role IN (" + ", ".join(f"'{role}'" for role in _ROLES) + ")",
            name="ck_workspace_memberships_role",
        ),
    )
    for column in ("organization_id", "workspace_id", "user_id"):
        op.create_index(f"ix_workspace_memberships_{column}", "workspace_memberships", [column])

    for table in ("users", "workspace_memberships"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(_USERS_POLICY)
    op.execute(_MEMBERSHIPS_POLICY)


def downgrade() -> None:
    op.drop_table("workspace_memberships")
    op.drop_table("users")
    for function in _SETTING_FUNCTIONS:
        op.execute(f"DROP FUNCTION {function}()")
