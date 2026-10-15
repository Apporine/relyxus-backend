"""Workspace incidents table with lifecycle CHECK constraints (MPS-8A.07, ADR-0004).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-15
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LIFECYCLE_STATES = (
    "triage",
    "investigating",
    "mitigating",
    "monitoring",
    "resolved",
    "closed",
    "cancelled",
    "merged",
)
_SEVERITIES = ("sev1", "sev2", "sev3", "sev4")


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    lifecycle_check = "lifecycle_state IN (" + ", ".join(f"'{s}'" for s in _LIFECYCLE_STATES) + ")"
    severity_check = "severity IN (" + ", ".join(f"'{s}'" for s in _SEVERITIES) + ")"

    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("lifecycle_state", sa.String(32), server_default="triage", nullable=False),
        sa.Column("severity", sa.String(8), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_incidents"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_incidents_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_incidents_workspace_organization",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(lifecycle_check, name="lifecycle_state"),
        sa.CheckConstraint(severity_check, name="severity"),
        sa.CheckConstraint(
            "char_length(title) >= 1 AND char_length(title) <= 500",
            name="title_length",
        ),
    )
    op.create_index(
        "ix_incidents_workspace_id_lifecycle_state",
        "incidents",
        ["workspace_id", "lifecycle_state"],
    )
    op.create_index("ix_incidents_organization_id", "incidents", ["organization_id"])

    op.execute("ALTER TABLE incidents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE incidents FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY incidents_tenant_isolation ON incidents
        USING (organization_id = relyxus_current_organization_id())
        WITH CHECK (organization_id = relyxus_current_organization_id())
        """
    )


def downgrade() -> None:
    op.drop_table("incidents")
