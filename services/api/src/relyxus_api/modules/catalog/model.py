"""The service catalogue: technical services of a workspace (MPS-14.01, MPS-20.08).

Called `CatalogService` in code so it is never confused with the service layer. Owned by
an optional team of the same workspace. Archived services keep their values and stay
readable; they cannot be newly linked to incidents.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns

SERVICE_NAME_MAX_LENGTH = 200
SERVICE_DESCRIPTION_MAX_LENGTH = 2000
SERVICE_KEY_PATTERN = "^[a-z][a-z0-9-]{1,62}$"
ENVIRONMENT_PATTERN = "^[a-z][a-z0-9-]{0,31}$"
LABEL_KEY_PATTERN = "^[a-z0-9][a-z0-9._/-]{0,62}$"
LABEL_VALUE_MAX_LENGTH = 200
MAX_LABELS = 50


class ServiceTier(StrEnum):
    """Provisional scale, tier 1 most critical (register Q-41); MPS-20.08 names no values."""

    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    TIER_4 = "tier_4"


_TIERS_SQL = ", ".join(f"'{tier.value}'" for tier in ServiceTier)


class CatalogService(RecordColumns, Base):
    __tablename__ = "services"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_services_workspace_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["owner_team_id", "workspace_id"],
            ["teams.id", "teams.workspace_id"],
            name="fk_services_owner_team_same_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("workspace_id", "key", name="uq_services_workspace_id_key"),
        # Target for composite foreign keys (incidents' affected services).
        UniqueConstraint("id", "workspace_id", name="uq_services_id_workspace_id"),
        CheckConstraint(f"key ~ '{SERVICE_KEY_PATTERN}'", name="key_format"),
        CheckConstraint(f"environment ~ '{ENVIRONMENT_PATTERN}'", name="environment_format"),
        CheckConstraint(f"tier IN ({_TIERS_SQL})", name="tier"),
        CheckConstraint("char_length(name) >= 1", name="name_length"),
        CheckConstraint("jsonb_typeof(labels) = 'object'", name="labels_object"),
        Index("ix_services_organization_id", "organization_id"),
        Index("ix_services_owner_team_id", "owner_team_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    key: Mapped[str] = mapped_column(String(63))
    name: Mapped[str] = mapped_column(String(SERVICE_NAME_MAX_LENGTH))
    description: Mapped[str | None] = mapped_column(String(SERVICE_DESCRIPTION_MAX_LENGTH))
    tier: Mapped[str] = mapped_column(String(16))
    environment: Mapped[str] = mapped_column(String(32))
    owner_team_id: Mapped[uuid.UUID | None]
    labels: Mapped[dict[str, str]] = mapped_column(JSONB)
    archived_at: Mapped[datetime | None]
