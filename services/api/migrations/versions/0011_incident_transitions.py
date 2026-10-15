"""Lifecycle timestamps and merge target for incident transitions (MPS-8A.09-8A.20).

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-15

Adds `mitigated_at`, `resolved_at`, `closed_at`, `cancelled_at` (MPS-8A.20 metric
timestamps) and `merged_into_incident_id`. A composite foreign key to
`incidents(id, workspace_id)` means an incident can only be merged into another incident of
the same workspace, and a merged incident must name its target.

Rollout: expand only. Existing rows are never `merged`, so the new CHECKs hold.
Rollback plan: the previous release ignores the new columns and cannot reach `merged`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIMESTAMP_COLUMNS = ("mitigated_at", "resolved_at", "closed_at", "cancelled_at")
_UNIQUE_ID_WORKSPACE = "uq_incidents_id_workspace_id"
_MERGE_FOREIGN_KEY = "fk_incidents_merged_into_same_workspace"
_MERGE_TARGET_CHECK = "ck_incidents_merged_has_target"
_NOT_SELF_CHECK = "ck_incidents_not_merged_into_self"


def upgrade() -> None:
    for column in _TIMESTAMP_COLUMNS:
        op.add_column("incidents", sa.Column(column, sa.DateTime(timezone=True)))
    op.add_column("incidents", sa.Column("merged_into_incident_id", sa.Uuid()))
    op.create_unique_constraint(_UNIQUE_ID_WORKSPACE, "incidents", ["id", "workspace_id"])
    op.create_foreign_key(
        _MERGE_FOREIGN_KEY,
        "incidents",
        "incidents",
        ["merged_into_incident_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        _MERGE_TARGET_CHECK,
        "incidents",
        "(lifecycle_state = 'merged') = (merged_into_incident_id IS NOT NULL)",
    )
    op.create_check_constraint(
        _NOT_SELF_CHECK, "incidents", "merged_into_incident_id IS DISTINCT FROM id"
    )
    op.create_index(
        "ix_incidents_merged_into_incident_id", "incidents", ["merged_into_incident_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_incidents_merged_into_incident_id", "incidents")
    op.drop_constraint(_NOT_SELF_CHECK, "incidents", type_="check")
    op.drop_constraint(_MERGE_TARGET_CHECK, "incidents", type_="check")
    op.drop_constraint(_MERGE_FOREIGN_KEY, "incidents", type_="foreignkey")
    op.drop_constraint(_UNIQUE_ID_WORKSPACE, "incidents", type_="unique")
    op.drop_column("incidents", "merged_into_incident_id")
    for column in _TIMESTAMP_COLUMNS:
        op.drop_column("incidents", column)
