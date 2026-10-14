"""Append-only hash-chained audit events with row-level security.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-14

Rollout: expand only (new table, functions, triggers); safe with the previous release.
Rollback plan: the previous release does not read audit_events, so it runs unchanged.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMMUTABLE_TRIGGER = """
CREATE OR REPLACE FUNCTION relyxus_audit_events_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_events are append-only';
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
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("chain_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("effective_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("before_state", JSONB(), nullable=True),
        sa.Column("after_state", JSONB(), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_audit_events_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("chain_id", "sequence", name="uq_audit_events_chain_id_sequence"),
        sa.CheckConstraint("sequence >= 1", name="ck_audit_events_sequence_positive"),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system', 'support')", name="ck_audit_events_actor_type"
        ),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'denied', 'failed')", name="ck_audit_events_outcome"
        ),
    )
    op.create_index("ix_audit_events_workspace_id", "audit_events", ["workspace_id"])
    op.create_index(
        "ix_audit_events_organization_id_occurred_at",
        "audit_events",
        ["organization_id", "occurred_at"],
    )

    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_events_tenant_isolation ON audit_events
        USING (organization_id = relyxus_current_organization_id())
        WITH CHECK (organization_id = relyxus_current_organization_id())
        """
    )

    op.execute(_IMMUTABLE_TRIGGER)
    op.execute(
        """
        CREATE TRIGGER audit_events_no_update
        BEFORE UPDATE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION relyxus_audit_events_immutable()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_no_delete
        BEFORE DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION relyxus_audit_events_immutable()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_delete ON audit_events")
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS relyxus_audit_events_immutable()")
    op.drop_table("audit_events")
