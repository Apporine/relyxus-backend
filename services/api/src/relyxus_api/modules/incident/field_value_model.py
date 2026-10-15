"""Custom field values on incidents (MPS-20.28).

One current value per incident and field, with the field version it was set under. The
history of every change is on the incident timeline and in the audit chain.
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns


class IncidentFieldValue(RecordColumns, Base):
    __tablename__ = "incident_field_values"
    __table_args__ = (
        ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_field_values_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["field_id", "workspace_id"],
            ["custom_field_definitions.id", "custom_field_definitions.workspace_id"],
            name="fk_incident_field_values_field_same_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "incident_id", "field_id", name="uq_incident_field_values_incident_id_field_id"
        ),
        Index("ix_incident_field_values_field_id", "field_id"),
        Index("ix_incident_field_values_organization_id", "organization_id"),
        Index("ix_incident_field_values_workspace_id", "workspace_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    incident_id: Mapped[uuid.UUID]
    field_id: Mapped[uuid.UUID]
    field_version: Mapped[int]
    # Canonical JSON only (no floats): numbers are decimal strings, money is minor units.
    value: Mapped[Any] = mapped_column(JSONB)
    set_by_user_id: Mapped[uuid.UUID]
