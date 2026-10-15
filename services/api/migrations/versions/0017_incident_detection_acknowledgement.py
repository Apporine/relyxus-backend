"""Impact-started, detected and acknowledged metric timestamps (MPS-8A.20).

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-15

Adds `impact_started_at`, `detected_at`, `acknowledged_at` and `acknowledged_by_user_id`.
CHECKs: impact cannot start after detection, and an acknowledgement always names who made
it.

Rollout: expand only; all columns nullable. Existing incidents keep NULL (unknown), which
the API reports as such; no backfill is invented. Rollback plan: the previous release
ignores the new columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIMESTAMP_COLUMNS = ("impact_started_at", "detected_at", "acknowledged_at")
_IMPACT_CHECK = "ck_incidents_impact_not_after_detection"
_ACKNOWLEDGED_CHECK = "ck_incidents_acknowledged_has_actor"


def upgrade() -> None:
    for column in _TIMESTAMP_COLUMNS:
        op.add_column("incidents", sa.Column(column, sa.DateTime(timezone=True)))
    op.add_column("incidents", sa.Column("acknowledged_by_user_id", sa.Uuid()))
    op.create_check_constraint(
        _IMPACT_CHECK,
        "incidents",
        "impact_started_at IS NULL OR detected_at IS NULL OR impact_started_at <= detected_at",
    )
    op.create_check_constraint(
        _ACKNOWLEDGED_CHECK,
        "incidents",
        "(acknowledged_at IS NULL) = (acknowledged_by_user_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(_ACKNOWLEDGED_CHECK, "incidents", type_="check")
    op.drop_constraint(_IMPACT_CHECK, "incidents", type_="check")
    op.drop_column("incidents", "acknowledged_by_user_id")
    for column in reversed(_TIMESTAMP_COLUMNS):
        op.drop_column("incidents", column)
