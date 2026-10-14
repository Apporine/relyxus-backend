"""Commercial customer binding on organisations (MPS-29.06, LIC-17.02).

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("customer_id", sa.Uuid(), nullable=True))
    op.create_index("ix_organizations_customer_id", "organizations", ["customer_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_organizations_customer_id", table_name="organizations")
    op.drop_column("organizations", "customer_id")
