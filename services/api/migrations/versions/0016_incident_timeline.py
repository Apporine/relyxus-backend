"""Incident timeline events (MPS-5.20, MPS-8A.33, MPS-11.20).

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-15

Append-only: triggers reject UPDATE and DELETE, as for audit_events. Events belong to an
incident through a composite foreign key to incidents(id, workspace_id); forced RLS by
organisation as for incidents. `sequence` orders events strictly.

Rollout: expand only (new table). Existing incidents start with an empty timeline; their
history stays in the audit chain. Rollback plan: the previous release does not read it.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "incident_timeline_events"
_IMMUTABLE_FUNCTION = """
CREATE OR REPLACE FUNCTION relyxus_incident_timeline_events_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'incident_timeline_events are append-only';
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
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("before_state", JSONB(), nullable=True),
        sa.Column("after_state", JSONB(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_incident_timeline_events"),
        sa.UniqueConstraint("sequence", name="uq_incident_timeline_events_sequence"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_incident_timeline_events_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_timeline_events_incident_same_workspace",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_incident_timeline_events_incident_id_sequence", _TABLE, ["incident_id", "sequence"]
    )
    for column in ("organization_id", "workspace_id"):
        op.create_index(f"ix_{_TABLE}_{column}", _TABLE, [column])
    op.execute(_IMMUTABLE_FUNCTION)
    for operation in ("update", "delete"):
        op.execute(
            f"CREATE TRIGGER {_TABLE}_no_{operation} BEFORE {operation.upper()} ON {_TABLE}"
            " FOR EACH ROW EXECUTE FUNCTION relyxus_incident_timeline_events_immutable()"
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
    op.execute("DROP FUNCTION IF EXISTS relyxus_incident_timeline_events_immutable()")
