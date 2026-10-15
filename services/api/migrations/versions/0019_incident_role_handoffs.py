"""Incident role handoffs (MPS-11.23, MPS-11.24, MPS-20.33).

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-15

A partial unique index allows at most one pending handoff per role of an incident. The
package snapshot is JSONB, captured at request time. Composite FK to the incident; forced
RLS by organisation as for incidents.

Rollout: expand only (new table). Rollback plan: the previous release does not read it.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "incident_role_handoffs"


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
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("from_user_id", sa.Uuid(), nullable=False),
        sa.Column("to_user_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("package_snapshot", JSONB(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_incident_role_handoffs"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_incident_role_handoffs_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_role_handoffs_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["from_user_id"],
            ["users.id"],
            name="fk_incident_role_handoffs_from_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_user_id"],
            ["users.id"],
            name="fk_incident_role_handoffs_to_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "role IN ('incident_commander', 'communications_lead', 'scribe')",
            name="ck_incident_role_handoffs_role",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'accepted', 'cancelled')", name="ck_incident_role_handoffs_state"
        ),
        sa.CheckConstraint(
            "from_user_id <> to_user_id", name="ck_incident_role_handoffs_different_people"
        ),
        sa.CheckConstraint(
            "(state = 'accepted') = (accepted_at IS NOT NULL)",
            name="ck_incident_role_handoffs_accepted_has_time",
        ),
        sa.CheckConstraint(
            "(state = 'cancelled') = (cancelled_at IS NOT NULL)",
            name="ck_incident_role_handoffs_cancelled_has_time",
        ),
    )
    op.create_index(
        "uq_incident_role_handoffs_pending_role",
        _TABLE,
        ["incident_id", "role"],
        unique=True,
        postgresql_where=sa.text("state = 'pending'"),
    )
    op.create_index("ix_incident_role_handoffs_incident_id_id", _TABLE, ["incident_id", "id"])
    for column in ("organization_id", "workspace_id"):
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
