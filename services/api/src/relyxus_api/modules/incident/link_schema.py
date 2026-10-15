import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from relyxus_api.modules.incident.link_model import IncidentLink, IncidentLinkType


class LinkDirection(StrEnum):
    OUTGOING = "outgoing"
    INCOMING = "incoming"


class AddIncidentLinkRequest(BaseModel):
    """Read as "this incident is `link_type` the target incident"."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_incident_id: uuid.UUID = Field(examples=["0192f0c4-7d1e-7a3b-9c2d-5e6f7a8b9c0d"])
    link_type: IncidentLinkType = Field(examples=[IncidentLinkType.CAUSED_BY])


class IncidentLinkView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    link_type: IncidentLinkType
    direction: LinkDirection = Field(
        description=(
            "`outgoing`: this incident is `link_type` the other incident. "
            "`incoming`: the other incident is `link_type` this one."
        )
    )
    from_incident_id: uuid.UUID
    to_incident_id: uuid.UUID
    other_incident_id: uuid.UUID
    created_by_user_id: uuid.UUID
    created_at: datetime

    @classmethod
    def from_link(cls, link: IncidentLink, viewed_from: uuid.UUID) -> "IncidentLinkView":
        is_outgoing = link.from_incident_id == viewed_from
        return cls(
            id=link.id,
            link_type=IncidentLinkType(link.link_type),
            direction=LinkDirection.OUTGOING if is_outgoing else LinkDirection.INCOMING,
            from_incident_id=link.from_incident_id,
            to_incident_id=link.to_incident_id,
            other_incident_id=link.to_incident_id if is_outgoing else link.from_incident_id,
            created_by_user_id=link.created_by_user_id,
            created_at=link.created_at,
        )
