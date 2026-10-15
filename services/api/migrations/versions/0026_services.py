"""The service catalogue (MPS-14.01, MPS-20.08).

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-15

Services belong to a workspace; the optional owner team references teams(id,
workspace_id), so it can only be a team of the same workspace. Keys are unique per
workspace; labels are a JSON object. Forced RLS by organisation.

Rollout: expand only (new table). Rollback plan: the previous release does not read it.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(63), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("owner_team_id", sa.Uuid(), nullable=True),
        sa.Column("labels", JSONB(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_services"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_services_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_services_workspace_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_team_id", "workspace_id"],
            ["teams.id", "teams.workspace_id"],
            name="fk_services_owner_team_same_workspace",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("workspace_id", "key", name="uq_services_workspace_id_key"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_services_id_workspace_id"),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9-]{1,62}$'", name="ck_services_key_format"),
        sa.CheckConstraint(
            "environment ~ '^[a-z][a-z0-9-]{0,31}$'", name="ck_services_environment_format"
        ),
        sa.CheckConstraint(
            "tier IN ('tier_1', 'tier_2', 'tier_3', 'tier_4')", name="ck_services_tier"
        ),
        sa.CheckConstraint("char_length(name) >= 1", name="ck_services_name_length"),
        sa.CheckConstraint("jsonb_typeof(labels) = 'object'", name="ck_services_labels_object"),
    )
    for column in ("organization_id", "owner_team_id"):
        op.create_index(f"ix_services_{column}", "services", [column])
    op.execute("ALTER TABLE services ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE services FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY services_tenant_isolation ON services"
        " USING (organization_id = relyxus_current_organization_id())"
        " WITH CHECK (organization_id = relyxus_current_organization_id())"
    )


def downgrade() -> None:
    op.drop_table("services")
