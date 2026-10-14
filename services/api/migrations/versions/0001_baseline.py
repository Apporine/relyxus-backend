"""Baseline: empty starting point for the Relyxus schema.

Revision ID: 0001
Revises:
Create Date: 2026-10-14

Rollout: forward-only in shared environments; expand first, contract in a later release so
the previous application version keeps working (ADR-0003 §6, MPS-6A.08).
Rollback plan: nothing to roll back.
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
