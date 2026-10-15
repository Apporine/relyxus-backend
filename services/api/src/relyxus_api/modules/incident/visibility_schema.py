import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.incident.access_grant_model import (
    GRANT_REASON_MAX_LENGTH,
    IncidentAccessGrant,
)
from relyxus_api.modules.incident.model import IncidentVisibility

GrantReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=GRANT_REASON_MAX_LENGTH),
]


class ChangeVisibilityRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    visibility: IncidentVisibility = Field(examples=[IncidentVisibility.RESTRICTED])
    reason: GrantReason = Field(examples=["Suspected insider involvement"])


class CreateAccessGrantRequest(BaseModel):
    """Name exactly one of `user_id`, `team_id` or `role`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = Field(
        default=None, description="Counts only while the incident is `restricted`."
    )
    role: WorkspaceRole | None = Field(
        default=None, description="Counts only while the incident is `restricted`."
    )
    reason: GrantReason = Field(examples=["Fraud team lead needs the timeline"])
    expires_at: AwareDatetime | None = Field(default=None, examples=["2026-10-22T00:00:00Z"])

    @model_validator(mode="after")
    def _exactly_one_grantee(self) -> Self:
        named = [value for value in (self.user_id, self.team_id, self.role) if value is not None]
        if len(named) != 1:
            raise ValueError("Name exactly one of user_id, team_id or role.")
        return self


class AccessGrantView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    team_id: uuid.UUID | None
    role: WorkspaceRole | None
    reason: str
    expires_at: datetime | None
    granted_by_user_id: uuid.UUID
    granted_at: datetime

    @classmethod
    def from_grant(cls, grant: IncidentAccessGrant) -> "AccessGrantView":
        return cls(
            id=grant.id,
            user_id=grant.user_id,
            team_id=grant.team_id,
            role=None if grant.role is None else WorkspaceRole(grant.role),
            reason=grant.reason,
            expires_at=grant.expires_at,
            granted_by_user_id=grant.granted_by_user_id,
            granted_at=grant.created_at,
        )
