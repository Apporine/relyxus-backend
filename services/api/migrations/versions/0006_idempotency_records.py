"""Persist idempotent POST replay payloads per organisation (ADR-0003 §5).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-14
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_method", sa.String(16), nullable=False),
        sa.Column("request_path", sa.String(256), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", JSONB(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_idempotency_records_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_idempotency_records_organization_id_idempotency_key",
        ),
    )
    op.create_index(
        "ix_idempotency_records_organization_id_created_at",
        "idempotency_records",
        ["organization_id", "created_at"],
    )

    op.execute("ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE idempotency_records FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY idempotency_records_tenant_isolation ON idempotency_records
        USING (organization_id = relyxus_current_organization_id())
        WITH CHECK (organization_id = relyxus_current_organization_id())
        """
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
