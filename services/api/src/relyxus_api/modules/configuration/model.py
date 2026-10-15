"""Configuration versions (MPS-14A.07, MPS-20.29, MPS-8A.06).

Every change to a configuration object (team, service, incident type, custom field, ...)
writes one immutable version: who, when, from where, the full state after the change
and the exact difference. Versions are numbered per object from 1. Rows are never
updated or deleted: database triggers reject both (migration 0029).
"""

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns


class ConfigurationObjectType(StrEnum):
    TEAM = "team"
    SERVICE = "service"
    INCIDENT_TYPE = "incident_type"
    CUSTOM_FIELD = "custom_field"


class ConfigurationSource(StrEnum):
    """MPS-20.29 sources. Only the API exists today; the console calls the API."""

    API = "api"
    UI = "ui"
    TERRAFORM = "terraform"


def _values_sql(values: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in values)


class ConfigurationVersion(RecordColumns, Base):
    __tablename__ = "configuration_versions"
    __table_args__ = (
        UniqueConstraint(
            "object_type",
            "object_id",
            "version",
            name="uq_configuration_versions_object_type_object_id_version",
        ),
        CheckConstraint(
            f"object_type IN ({_values_sql(ConfigurationObjectType)})", name="object_type"
        ),
        CheckConstraint(f"source IN ({_values_sql(ConfigurationSource)})", name="source"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_configuration_versions_organization_id", "organization_id"),
        Index("ix_configuration_versions_workspace_id", "workspace_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    object_type: Mapped[str] = mapped_column(String(32))
    object_id: Mapped[uuid.UUID]
    version: Mapped[int]
    source: Mapped[str] = mapped_column(String(16))
    actor_user_id: Mapped[uuid.UUID | None]
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    difference: Mapped[dict[str, Any]] = mapped_column(JSONB)
