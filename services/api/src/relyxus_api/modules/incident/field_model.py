"""Custom field definitions (MPS-8A.03, MPS-8A.04, MPS-8A.05, MPS-20.27).

A field is configuration: every change bumps `version` and writes a configuration
version. Deleting archives the field; values already set stay (MPS-8A.05). A field can
show only for some incident types and severities (MPS-8A.04) and be required from a
lifecycle stage on.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

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

from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.shared.db.base import Base, RecordColumns

FIELD_LABEL_MAX_LENGTH = 200
FIELD_DESCRIPTION_MAX_LENGTH = 2000
FIELD_KEY_PATTERN = "^[a-z][a-z0-9_]{1,62}$"
MAX_OPTIONS = 100
OPTION_LABEL_MAX_LENGTH = 200


class FieldDataType(StrEnum):
    """MPS-8A.03 library; `vendor` arrives with the vendor catalogue (MPS-20.09)."""

    TEXT = "text"
    NUMBER = "number"
    CURRENCY = "currency"
    DATE_TIME = "date_time"
    YES_NO = "yes_no"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    USER = "user"
    TEAM = "team"
    SERVICE = "service"
    URL = "url"


CHOICE_TYPES = frozenset({FieldDataType.SINGLE_CHOICE, FieldDataType.MULTIPLE_CHOICE})

# Stages a field can be required at, in lifecycle order (triage drafts never require).
REQUIRABLE_STAGES: tuple[IncidentLifecycleState, ...] = (
    IncidentLifecycleState.INVESTIGATING,
    IncidentLifecycleState.MITIGATING,
    IncidentLifecycleState.MONITORING,
    IncidentLifecycleState.RESOLVED,
    IncidentLifecycleState.CLOSED,
)


def _values_sql(values: tuple[StrEnum, ...] | type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in values)


class CustomFieldDefinition(RecordColumns, Base):
    __tablename__ = "custom_field_definitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "organization_id"],
            ["workspaces.id", "workspaces.organization_id"],
            name="fk_custom_field_definitions_workspace_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "workspace_id", "key", name="uq_custom_field_definitions_workspace_id_key"
        ),
        UniqueConstraint("id", "workspace_id", name="uq_custom_field_definitions_id_workspace_id"),
        CheckConstraint(f"key ~ '{FIELD_KEY_PATTERN}'", name="key_format"),
        CheckConstraint("char_length(label) >= 1", name="label_length"),
        CheckConstraint(f"data_type IN ({_values_sql(FieldDataType)})", name="data_type"),
        CheckConstraint(
            f"required_at_stage IS NULL OR required_at_stage IN ({_values_sql(REQUIRABLE_STAGES)})",
            name="required_at_stage",
        ),
        CheckConstraint("jsonb_typeof(options) = 'array'", name="options_array"),
        CheckConstraint("jsonb_typeof(display_condition) = 'object'", name="condition_object"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_custom_field_definitions_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    key: Mapped[str] = mapped_column(String(63))
    label: Mapped[str] = mapped_column(String(FIELD_LABEL_MAX_LENGTH))
    description: Mapped[str | None] = mapped_column(String(FIELD_DESCRIPTION_MAX_LENGTH))
    data_type: Mapped[str] = mapped_column(String(16))
    # Choice options as [{"value": "...", "label": "..."}]; empty for other types.
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    # {"incident_type_ids": [...], "severities": [...]}; empty lists mean "any".
    display_condition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    required_at_stage: Mapped[str | None] = mapped_column(String(16))
    version: Mapped[int]
    archived_at: Mapped[datetime | None]
