"""Custom field values on incidents (MPS-20.28).

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-15

One current value per (incident, field), with the field version it was set under; both
ends use composite FKs with the row's workspace. Forced RLS by organisation.

Rollout: expand only (new table). Rollback plan: the previous release does not read it.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "incident_field_values"


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
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("field_id", sa.Uuid(), nullable=False),
        sa.Column("field_version", sa.Integer(), nullable=False),
        sa.Column("value", JSONB(), nullable=False),
        sa.Column("set_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_incident_field_values"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_incident_field_values_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_field_values_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["field_id", "workspace_id"],
            ["custom_field_definitions.id", "custom_field_definitions.workspace_id"],
            name="fk_incident_field_values_field_same_workspace",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "incident_id", "field_id", name="uq_incident_field_values_incident_id_field_id"
        ),
    )
    for column in ("field_id", "organization_id", "workspace_id"):
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column])
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {_TABLE}_tenant_isolation ON {_TABLE}"
        " USING (organization_id = relyxus_current_organization_id())"
        " WITH CHECK (organization_id = relyxus_current_organization_id())"
    )


def downgrade() -> None:
    op.drop_table(_TABLE)
