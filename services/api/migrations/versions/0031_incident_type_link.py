"""Incidents record their type and type version (MPS-8A.06, MPS-8A.08, MPS-20.12).

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-15

Adds `incidents.incident_type_id` (composite FK to incident_types(id, workspace_id), so a
type of another workspace can never be referenced) and `incident_type_version`, with a
CHECK that both are set or both are NULL, and an index for filtering by type.

Rollout: expand only; nullable columns, existing incidents have no type. Rollback plan:
the previous release ignores the columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FOREIGN_KEY = "fk_incidents_incident_type_same_workspace"
_CHECK = "ck_incidents_type_has_version"
_INDEX = "ix_incidents_incident_type_id"


def upgrade() -> None:
    op.add_column("incidents", sa.Column("incident_type_id", sa.Uuid(), nullable=True))
    op.add_column("incidents", sa.Column("incident_type_version", sa.Integer(), nullable=True))
    op.create_foreign_key(
        _FOREIGN_KEY,
        "incidents",
        "incident_types",
        ["incident_type_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        _CHECK, "incidents", "(incident_type_id IS NULL) = (incident_type_version IS NULL)"
    )
    op.create_index(_INDEX, "incidents", ["incident_type_id"])


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="incidents")
    op.drop_constraint(_CHECK, "incidents", type_="check")
    op.drop_constraint(_FOREIGN_KEY, "incidents", type_="foreignkey")
    op.drop_column("incidents", "incident_type_version")
    op.drop_column("incidents", "incident_type_id")
