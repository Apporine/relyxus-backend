"""Store installed commercial licence artifacts per organisation (LIC-7.07).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-14
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    op.create_table(
        "organization_licenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("license_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("artifact", sa.Text(), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_organization_licenses"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_licenses_organization_id_organizations",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_organization_licenses_organization_id_is_current",
        "organization_licenses",
        ["organization_id", "is_current"],
    )

    op.execute("ALTER TABLE organization_licenses ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organization_licenses FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY organization_licenses_tenant_isolation ON organization_licenses
        USING (organization_id = relyxus_current_organization_id())
        WITH CHECK (organization_id = relyxus_current_organization_id())
        """
    )


def downgrade() -> None:
    op.drop_table("organization_licenses")
