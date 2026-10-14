"""Organisations and workspaces with forced row-level security.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14

Rollout: expand only (new tables and functions); safe with the previous release.
Rollback plan: the previous release does not read these tables, so it runs unchanged.

Security: RLS is ENABLED and FORCED, so policies also bind the table owner. PostgreSQL
superusers and BYPASSRLS roles still bypass RLS; the API therefore reports not-ready
outside local environments when it connects with such a role.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RECORD_COLUMNS = (
    ("created_at", "now()"),
    ("updated_at", "now()"),
)


def _record_columns() -> list[sa.Column[datetime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text(default), nullable=False)
        for name, default in _RECORD_COLUMNS
    ]


def upgrade() -> None:
    # Missing or empty context yields NULL, and NULL never equals an ID: fail closed.
    op.execute(
        """
        CREATE FUNCTION relyxus_current_organization_id() RETURNS uuid
        LANGUAGE sql STABLE AS
        $$ SELECT NULLIF(current_setting('app.organization_id', true), '')::uuid $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION relyxus_current_workspace_id() RETURNS uuid
        LANGUAGE sql STABLE AS
        $$ SELECT NULLIF(current_setting('app.workspace_id', true), '')::uuid $$
        """
    )
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("deployment_mode", sa.String(20), nullable=False),
        sa.Column("default_region", sa.String(64), nullable=False),
        *_record_columns(),
        sa.CheckConstraint(
            "deployment_mode IN ('saas', 'dedicated', 'self_hosted', 'air_gapped')",
            name="ck_organizations_deployment_mode",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(63), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("data_residency_region", sa.String(64), nullable=False),
        *_record_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_workspaces_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organization_id", "key", name="uq_workspaces_organization_id_key"),
        sa.UniqueConstraint("id", "organization_id", name="uq_workspaces_id_organization_id"),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9-]{1,62}$'", name="ck_workspaces_key_format"),
    )
    op.create_index("ix_workspaces_organization_id", "workspaces", ["organization_id"])

    for table, column in (("organizations", "id"), ("workspaces", "organization_id")):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING ({column} = relyxus_current_organization_id())
            WITH CHECK ({column} = relyxus_current_organization_id())
            """
        )


def downgrade() -> None:
    op.drop_table("workspaces")
    op.drop_table("organizations")
    op.execute("DROP FUNCTION relyxus_current_workspace_id()")
    op.execute("DROP FUNCTION relyxus_current_organization_id()")
