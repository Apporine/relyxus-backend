"""Live incident tasks (MPS-11.14-11.22, MPS-20.32).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-15

Tasks belong to an incident through a composite foreign key to incidents(id, workspace_id),
so a task can never sit under another workspace's incident; forced RLS by organisation as
for incidents. Priority values are provisional (register Q-35).

Rollout: expand only (new table). Rollback plan: the previous release does not read it.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "incident_tasks"


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
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("cancellation_reason", sa.String(1000), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_incident_tasks"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_incident_tasks_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_tasks_incident_same_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_incident_tasks_owner_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("char_length(title) >= 1", name="ck_incident_tasks_title_length"),
        sa.CheckConstraint(
            "priority IN ('high', 'medium', 'low')", name="ck_incident_tasks_priority"
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'blocked', 'done', 'cancelled')",
            name="ck_incident_tasks_status",
        ),
        sa.CheckConstraint("source IN ('manual')", name="ck_incident_tasks_source"),
        sa.CheckConstraint(
            "(status = 'cancelled') = (cancellation_reason IS NOT NULL)",
            name="ck_incident_tasks_cancelled_has_reason",
        ),
        sa.CheckConstraint(
            "(status = 'done') = (completed_at IS NOT NULL)",
            name="ck_incident_tasks_done_has_completion",
        ),
    )
    op.create_index("ix_incident_tasks_incident_id_id", _TABLE, ["incident_id", "id"])
    for column in ("organization_id", "workspace_id", "owner_user_id"):
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
