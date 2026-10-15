"""Incident role assignments: commander, communications lead, scribe (MPS-11.04).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-15

One current holder per incident and role. A composite foreign key to
`incidents(id, workspace_id)` keeps an assignment in its incident's own workspace. Forced
RLS by organisation, like incidents. History lives in the audit chain.

Rollout: expand only (new table). Rollback plan: the previous release does not read it.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "incident_role_assignments"


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
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_incident_role_assignments"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_incident_role_assignments_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_role_assignments_incident_same_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_incident_role_assignments_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "incident_id", "role", name="uq_incident_role_assignments_incident_id_role"
        ),
        sa.CheckConstraint(
            "role IN ('incident_commander', 'communications_lead', 'scribe')",
            name="ck_incident_role_assignments_role",
        ),
    )
    for column in ("organization_id", "workspace_id", "user_id"):
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column])
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {_TABLE}_tenant_isolation ON {_TABLE}
        USING (organization_id = relyxus_current_organization_id())
        WITH CHECK (organization_id = relyxus_current_organization_id())
        """
    )


def downgrade() -> None:
    op.drop_table(_TABLE)
