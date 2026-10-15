"""Post-incident follow-ups (MPS-26.02, MPS-13.17, MPS-20.32).

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-15

Composite FK to the incident; optional unique link to the live task it came from (a task
converts to at most one follow-up). CHECKs mirror incident_tasks: cancelled has a reason,
done has a completion time, and the source matches the task link. Forced RLS.

Rollout: expand only (new table). Rollback plan: the previous release does not read it.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "incident_follow_ups"


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
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("source_task_id", sa.Uuid(), nullable=True),
        sa.Column("cancellation_reason", sa.String(1000), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_incident_follow_ups"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_incident_follow_ups_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_follow_ups_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_incident_follow_ups_owner_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_task_id"],
            ["incident_tasks.id"],
            name="fk_incident_follow_ups_source_task_id_incident_tasks",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("source_task_id", name="uq_incident_follow_ups_source_task_id"),
        sa.CheckConstraint("char_length(title) >= 1", name="ck_incident_follow_ups_title_length"),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'done', 'cancelled')",
            name="ck_incident_follow_ups_status",
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'live_task')", name="ck_incident_follow_ups_source"
        ),
        sa.CheckConstraint(
            "(source = 'live_task') = (source_task_id IS NOT NULL)",
            name="ck_incident_follow_ups_source_task_matches",
        ),
        sa.CheckConstraint(
            "(status = 'cancelled') = (cancellation_reason IS NOT NULL)",
            name="ck_incident_follow_ups_cancelled_has_reason",
        ),
        sa.CheckConstraint(
            "(status = 'done') = (completed_at IS NOT NULL)",
            name="ck_incident_follow_ups_done_has_completion",
        ),
    )
    op.create_index("ix_incident_follow_ups_incident_id_id", _TABLE, ["incident_id", "id"])
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
