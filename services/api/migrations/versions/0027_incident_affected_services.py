"""Services affected by incidents (MPS-8A.08, MPS-20.12).

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-15

Both ends use composite foreign keys with the link's own workspace, so an incident can
only name services of its workspace. One row per (incident, service); an index on
service_id serves the incident list's service filter. Forced RLS by organisation.

Rollout: expand only (new table). Rollback plan: the previous release does not read it.
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "incident_affected_services"


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
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("added_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_incident_affected_services"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_incident_affected_services_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_affected_services_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id", "workspace_id"],
            ["services.id", "services.workspace_id"],
            name="fk_incident_affected_services_service_same_workspace",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "incident_id",
            "service_id",
            name="uq_incident_affected_services_incident_id_service_id",
        ),
    )
    for column in ("service_id", "organization_id", "workspace_id"):
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
