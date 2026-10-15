"""Incident types (MPS-8A.01, MPS-8A.02, MPS-20.26).

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-15

Types belong to a workspace; keys are unique per workspace. Allowed severities are a
non-empty JSON array containing the default severity. `version` is the current
configuration version. Forced RLS by organisation.

Rollout: expand only (new table). Default types are installed per workspace through the
API, not by the migration. Rollback plan: the previous release does not read the table.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "incident_types"


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(63), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("allowed_severities", JSONB(), nullable=False),
        sa.Column("default_severity", sa.String(8), nullable=False),
        sa.Column("default_visibility", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_incident_types"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_incident_types_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_incident_types_workspace_organization",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("workspace_id", "key", name="uq_incident_types_workspace_id_key"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_incident_types_id_workspace_id"),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9-]{1,62}$'", name="ck_incident_types_key_format"),
        sa.CheckConstraint("char_length(name) >= 1", name="ck_incident_types_name_length"),
        sa.CheckConstraint(
            "jsonb_typeof(allowed_severities) = 'array'"
            " AND jsonb_array_length(allowed_severities) >= 1",
            name="ck_incident_types_allowed_severities_not_empty",
        ),
        sa.CheckConstraint(
            "allowed_severities @> to_jsonb(default_severity)",
            name="ck_incident_types_default_severity_allowed",
        ),
        sa.CheckConstraint(
            "default_severity IN ('sev1', 'sev2', 'sev3', 'sev4')",
            name="ck_incident_types_default_severity",
        ),
        sa.CheckConstraint(
            "default_visibility IN ('workspace', 'restricted', 'invite_only', 'confidential')",
            name="ck_incident_types_default_visibility",
        ),
        sa.CheckConstraint("version >= 1", name="ck_incident_types_version_positive"),
    )
    op.create_index("ix_incident_types_organization_id", _TABLE, ["organization_id"])
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {_TABLE}_tenant_isolation ON {_TABLE}"
        " USING (organization_id = relyxus_current_organization_id())"
        " WITH CHECK (organization_id = relyxus_current_organization_id())"
    )


def downgrade() -> None:
    op.drop_table(_TABLE)
