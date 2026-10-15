"""Configuration versions (MPS-14A.07, MPS-20.29, MPS-8A.06).

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-15

One immutable row per change to a configuration object, numbered per object. Triggers
reject UPDATE and DELETE (as for audit_events). Forced RLS by organisation.

Rollout: expand only (new table). Objects created before this release have no version
history until their next change, which becomes version 1. Rollback plan: the previous
release does not read the table.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "configuration_versions"
_IMMUTABLE_FUNCTION = """
CREATE OR REPLACE FUNCTION relyxus_configuration_versions_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'configuration_versions are append-only';
END;
$$;
"""


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
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("difference", JSONB(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_configuration_versions"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_configuration_versions_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "object_type",
            "object_id",
            "version",
            name="uq_configuration_versions_object_type_object_id_version",
        ),
        sa.CheckConstraint(
            "object_type IN ('team', 'service', 'incident_type', 'custom_field')",
            name="ck_configuration_versions_object_type",
        ),
        sa.CheckConstraint(
            "source IN ('api', 'ui', 'terraform')", name="ck_configuration_versions_source"
        ),
        sa.CheckConstraint("version >= 1", name="ck_configuration_versions_version_positive"),
    )
    for column in ("organization_id", "workspace_id"):
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column])
    op.execute(_IMMUTABLE_FUNCTION)
    for operation in ("update", "delete"):
        op.execute(
            f"CREATE TRIGGER {_TABLE}_no_{operation} BEFORE {operation.upper()} ON {_TABLE}"
            " FOR EACH ROW EXECUTE FUNCTION relyxus_configuration_versions_immutable()"
        )
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {_TABLE}_tenant_isolation ON {_TABLE}"
        " USING (organization_id = relyxus_current_organization_id())"
        " WITH CHECK (organization_id = relyxus_current_organization_id())"
    )


def downgrade() -> None:
    op.drop_table(_TABLE)
    op.execute("DROP FUNCTION IF EXISTS relyxus_configuration_versions_immutable()")
