"""Index for listing a workspace's incidents newest first (MPS-15.02; context.md §9).

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-15

Rollout: expand only (a new index). Rollback plan: the previous release does not use it.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_incidents_workspace_id_id"


def upgrade() -> None:
    op.create_index(_INDEX, "incidents", ["workspace_id", "id"])


def downgrade() -> None:
    op.drop_index(_INDEX, "incidents")
