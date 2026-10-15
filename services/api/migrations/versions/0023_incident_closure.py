"""Closure details on incidents (MPS-8A.12, MPS-13.04, MPS-13.17).

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-15

Adds `closed_by_user_id`, `root_cause` (≤ 5000) and `closure_exception_reason` (≤ 1000),
and a CHECK that a closed incident has `closed_at`.

Rollout: expand only; nullable columns. No incident could be closed before this release,
so the CHECK holds for existing rows. Rollback plan: the previous release refuses to
close and ignores the columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLOSED_CHECK = "ck_incidents_closed_has_time"


def upgrade() -> None:
    op.add_column("incidents", sa.Column("closed_by_user_id", sa.Uuid()))
    op.add_column("incidents", sa.Column("root_cause", sa.String(5000)))
    op.add_column("incidents", sa.Column("closure_exception_reason", sa.String(1000)))
    op.create_check_constraint(
        _CLOSED_CHECK, "incidents", "lifecycle_state <> 'closed' OR closed_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_constraint(_CLOSED_CHECK, "incidents", type_="check")
    for column in ("closure_exception_reason", "root_cause", "closed_by_user_id"):
        op.drop_column("incidents", column)
