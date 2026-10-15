"""Incident types (MPS-8A.01, MPS-8A.02, MPS-8A.06, MPS-20.26).

A type is configuration: every change writes a configuration version, and `version` is
the type's current version number. Incidents record the type and the version they were
declared under, so later edits never change past incidents (MPS-15.04 "changes never
alter past incidents").

Today a type defines its allowed severities, default severity and default visibility.
Fields shown/required per stage arrive with custom fields; default roles, regulator
mappings, automations, forms and communication defaults arrive with those features.
"""

import uuid
from datetime import datetime

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

from relyxus_api.modules.incident.model import IncidentSeverity, IncidentVisibility
from relyxus_api.shared.db.base import Base, RecordColumns

TYPE_NAME_MAX_LENGTH = 200
TYPE_DESCRIPTION_MAX_LENGTH = 2000
TYPE_KEY_PATTERN = "^[a-z][a-z0-9-]{1,62}$"


def _values_sql(values: type[IncidentSeverity] | type[IncidentVisibility]) -> str:
    return ", ".join(f"'{member.value}'" for member in values)


class IncidentType(RecordColumns, Base):
    __tablename__ = "incident_types"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_incident_types_workspace_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("workspace_id", "key", name="uq_incident_types_workspace_id_key"),
        UniqueConstraint("id", "workspace_id", name="uq_incident_types_id_workspace_id"),
        CheckConstraint(f"key ~ '{TYPE_KEY_PATTERN}'", name="key_format"),
        CheckConstraint("char_length(name) >= 1", name="name_length"),
        CheckConstraint(
            "jsonb_typeof(allowed_severities) = 'array'"
            " AND jsonb_array_length(allowed_severities) >= 1",
            name="allowed_severities_not_empty",
        ),
        CheckConstraint(
            "allowed_severities @> to_jsonb(default_severity)", name="default_severity_allowed"
        ),
        CheckConstraint(
            f"default_severity IN ({_values_sql(IncidentSeverity)})", name="default_severity"
        ),
        CheckConstraint(
            f"default_visibility IN ({_values_sql(IncidentVisibility)})",
            name="default_visibility",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_incident_types_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    key: Mapped[str] = mapped_column(String(63))
    name: Mapped[str] = mapped_column(String(TYPE_NAME_MAX_LENGTH))
    description: Mapped[str | None] = mapped_column(String(TYPE_DESCRIPTION_MAX_LENGTH))
    allowed_severities: Mapped[list[str]] = mapped_column(JSONB)
    default_severity: Mapped[str] = mapped_column(String(8))
    default_visibility: Mapped[str] = mapped_column(String(16))
    version: Mapped[int]
    archived_at: Mapped[datetime | None]
