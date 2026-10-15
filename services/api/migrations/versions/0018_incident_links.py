"""Links between incidents (MPS-8A.31, MPS-20.31).

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-15

Both ends reference incidents(id, workspace_id) with the link's own workspace, so a link
can never cross workspaces. No self-links; one link per (from, to, type). Forced RLS by
organisation as for incidents.

Rollout: expand only (new table). Rollback plan: the previous release does not read it.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "incident_links"


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
        sa.Column("from_incident_id", sa.Uuid(), nullable=False),
        sa.Column("to_incident_id", sa.Uuid(), nullable=False),
        sa.Column("link_type", sa.String(32), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_incident_links"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_incident_links_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["from_incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_links_from_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_links_to_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "from_incident_id",
            "to_incident_id",
            "link_type",
            name="uq_incident_links_from_incident_id_to_incident_id_link_type",
        ),
        sa.CheckConstraint(
            "link_type IN ('duplicate_of', 'caused_by', 'related_to', 'recurrence_of')",
            name="ck_incident_links_link_type",
        ),
        sa.CheckConstraint("from_incident_id <> to_incident_id", name="ck_incident_links_not_self"),
    )
    for column in ("to_incident_id", "organization_id", "workspace_id"):
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
