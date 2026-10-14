"""Organisation and Workspace (MPS-14.01, MPS-20.02, MPS-20.03; ADR-0003 §6).

Both tables are protected by forced PostgreSQL row-level security (migration 0002). The
application sets the tenant context per transaction with `apply_tenant_context`.
"""

import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns

NAME_MAX_LENGTH = 200
REGION_MAX_LENGTH = 64
KEY_MAX_LENGTH = 63
WORKSPACE_KEY_PATTERN = "^[a-z][a-z0-9-]{1,62}$"


class DeploymentMode(StrEnum):
    """Exactly four modes (MPS-26.02)."""

    SAAS = "saas"
    DEDICATED = "dedicated"
    SELF_HOSTED = "self_hosted"
    AIR_GAPPED = "air_gapped"


_DEPLOYMENT_MODES_SQL = ", ".join(f"'{mode.value}'" for mode in DeploymentMode)


class Organization(RecordColumns, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(f"deployment_mode IN ({_DEPLOYMENT_MODES_SQL})", name="deployment_mode"),
    )

    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    deployment_mode: Mapped[str] = mapped_column(String(20))
    default_region: Mapped[str] = mapped_column(String(REGION_MAX_LENGTH))


class Workspace(RecordColumns, Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_workspaces_organization_id_key"),
        # Target for composite foreign keys from workspace-scoped tables, so a row can never
        # name a workspace that belongs to another organisation.
        UniqueConstraint("id", "organization_id", name="uq_workspaces_id_organization_id"),
        CheckConstraint(f"key ~ '{WORKSPACE_KEY_PATTERN}'", name="key_format"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    key: Mapped[str] = mapped_column(String(KEY_MAX_LENGTH))
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    data_residency_region: Mapped[str] = mapped_column(String(REGION_MAX_LENGTH))
