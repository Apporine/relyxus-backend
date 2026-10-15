"""Links between incidents of one workspace (MPS-8A.31, MPS-20.31).

"Merged into" stays on the incident itself (`merged_into_incident_id`, set by the merge
transition) and parent/child arrives with major incidents (MPS-8A.30), so neither is a
link type here.
"""

import uuid
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns


class IncidentLinkType(StrEnum):
    """Read as "<from incident> is <type> <to incident>"."""

    DUPLICATE_OF = "duplicate_of"
    CAUSED_BY = "caused_by"
    RELATED_TO = "related_to"
    RECURRENCE_OF = "recurrence_of"


_TYPES_SQL = ", ".join(f"'{link_type.value}'" for link_type in IncidentLinkType)


class IncidentLink(RecordColumns, Base):
    __tablename__ = "incident_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["from_incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_links_from_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["to_incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_links_to_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "from_incident_id",
            "to_incident_id",
            "link_type",
            name="uq_incident_links_from_incident_id_to_incident_id_link_type",
        ),
        CheckConstraint(f"link_type IN ({_TYPES_SQL})", name="link_type"),
        CheckConstraint("from_incident_id <> to_incident_id", name="not_self"),
        Index("ix_incident_links_to_incident_id", "to_incident_id"),
        Index("ix_incident_links_organization_id", "organization_id"),
        Index("ix_incident_links_workspace_id", "workspace_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    from_incident_id: Mapped[uuid.UUID]
    to_incident_id: Mapped[uuid.UUID]
    link_type: Mapped[str] = mapped_column(String(32))
    created_by_user_id: Mapped[uuid.UUID]
