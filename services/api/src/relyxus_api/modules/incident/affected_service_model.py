"""Services affected by an incident (MPS-8A.08, MPS-20.12, MPS-15.02 filter by service).

Both ends reference rows of the same workspace (composite foreign keys), so an incident
can only list services of its own workspace.
"""

import uuid

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns

MAX_AFFECTED_SERVICES = 50


class IncidentAffectedService(RecordColumns, Base):
    __tablename__ = "incident_affected_services"
    __table_args__ = (
        ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_affected_services_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["service_id", "workspace_id"],
            ["services.id", "services.workspace_id"],
            name="fk_incident_affected_services_service_same_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "incident_id",
            "service_id",
            name="uq_incident_affected_services_incident_id_service_id",
        ),
        Index("ix_incident_affected_services_service_id", "service_id"),
        Index("ix_incident_affected_services_organization_id", "organization_id"),
        Index("ix_incident_affected_services_workspace_id", "workspace_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    incident_id: Mapped[uuid.UUID]
    service_id: Mapped[uuid.UUID]
    added_by_user_id: Mapped[uuid.UUID]
