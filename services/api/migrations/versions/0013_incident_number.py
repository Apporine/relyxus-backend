"""Per-workspace incident numbers (MPS-20.12; ADR-0003 §4 display key, not an identifier).

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-15

Backfills existing incidents with 1..n per workspace in creation order, then makes the
column required and unique per workspace.

RLS on `incidents` is FORCED, so even the table owner would see no rows without tenant
context and the backfill would silently update nothing. The migration lifts FORCE only for
the backfill statement and restores it immediately, in the same transaction.

Rollout: expand (new column, backfilled). The previous release does not insert `number`,
so once it is NOT NULL the previous release can no longer create incidents: deploy this
release's API before running the migration (the upgrade plan's migration gate).
Rollback plan: downgrade drops the column; incident numbers are lost.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UNIQUE = "uq_incidents_workspace_id_number"
_CHECK = "ck_incidents_number_positive"


def upgrade() -> None:
    op.add_column("incidents", sa.Column("number", sa.Integer()))
    op.execute("ALTER TABLE incidents NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE incidents AS i SET number = ranked.position
        FROM (
            SELECT id, row_number() OVER (PARTITION BY workspace_id ORDER BY created_at, id)
                AS position
            FROM incidents
        ) AS ranked
        WHERE ranked.id = i.id
        """
    )
    op.execute("ALTER TABLE incidents FORCE ROW LEVEL SECURITY")
    op.alter_column("incidents", "number", nullable=False)
    op.create_unique_constraint(_UNIQUE, "incidents", ["workspace_id", "number"])
    op.create_check_constraint(_CHECK, "incidents", "number >= 1")


def downgrade() -> None:
    op.drop_constraint(_CHECK, "incidents", type_="check")
    op.drop_constraint(_UNIQUE, "incidents", type_="unique")
    op.drop_column("incidents", "number")
