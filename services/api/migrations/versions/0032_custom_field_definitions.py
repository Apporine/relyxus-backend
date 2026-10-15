"""Custom field definitions (MPS-8A.03, MPS-8A.04, MPS-8A.05, MPS-20.27).

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-15

Fields belong to a workspace; keys are unique per workspace. Options and display
conditions are JSON; `version` is the current configuration version. Forced RLS.

Rollout: expand only (new table). Rollback plan: the previous release does not read it.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "custom_field_definitions"
_DATA_TYPES = (
    "'text', 'number', 'currency', 'date_time', 'yes_no', 'single_choice', "
    "'multiple_choice', 'user', 'team', 'service', 'url'"
)
_STAGES = "'investigating', 'mitigating', 'monitoring', 'resolved', 'closed'"


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
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("data_type", sa.String(16), nullable=False),
        sa.Column("options", JSONB(), nullable=False),
        sa.Column("display_condition", JSONB(), nullable=False),
        sa.Column("required_at_stage", sa.String(16), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_custom_field_definitions"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_custom_field_definitions_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_custom_field_definitions_workspace_organization",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "workspace_id", "key", name="uq_custom_field_definitions_workspace_id_key"
        ),
        sa.UniqueConstraint(
            "id", "workspace_id", name="uq_custom_field_definitions_id_workspace_id"
        ),
        sa.CheckConstraint(
            "key ~ '^[a-z][a-z0-9_]{1,62}$'", name="ck_custom_field_definitions_key_format"
        ),
        sa.CheckConstraint(
            "char_length(label) >= 1", name="ck_custom_field_definitions_label_length"
        ),
        sa.CheckConstraint(
            f"data_type IN ({_DATA_TYPES})", name="ck_custom_field_definitions_data_type"
        ),
        sa.CheckConstraint(
            f"required_at_stage IS NULL OR required_at_stage IN ({_STAGES})",
            name="ck_custom_field_definitions_required_at_stage",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(options) = 'array'", name="ck_custom_field_definitions_options_array"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(display_condition) = 'object'",
            name="ck_custom_field_definitions_condition_object",
        ),
        sa.CheckConstraint("version >= 1", name="ck_custom_field_definitions_version_positive"),
    )
    op.create_index(f"ix_{_TABLE}_organization_id", _TABLE, ["organization_id"])
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {_TABLE}_tenant_isolation ON {_TABLE}"
        " USING (organization_id = relyxus_current_organization_id())"
        " WITH CHECK (organization_id = relyxus_current_organization_id())"
    )


def downgrade() -> None:
    op.drop_table(_TABLE)
