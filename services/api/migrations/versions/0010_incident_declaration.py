"""Record when and by whom an incident was declared (MPS-8A.08, MPS-8A.20).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-15

Adds `declared_at` and `declared_by_user_id`. A CHECK guarantees that every incident past
`triage` carries its declaration time, the "declared" metric timestamp of MPS-8A.20.

Rollout: expand only (nullable columns plus a CHECK that existing rows satisfy, because the
declare API did not exist before this release and every row is still `triage`).
Rollback plan: the previous release ignores the new columns and never writes past `triage`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "ck_incidents_declared_when_past_triage"


def upgrade() -> None:
    op.add_column("incidents", sa.Column("declared_at", sa.DateTime(timezone=True)))
    op.add_column("incidents", sa.Column("declared_by_user_id", sa.Uuid()))
    op.create_check_constraint(
        _CONSTRAINT,
        "incidents",
        "lifecycle_state = 'triage' OR declared_at IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "incidents", type_="check")
    op.drop_column("incidents", "declared_by_user_id")
    op.drop_column("incidents", "declared_at")
