import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.team.model import (
    TEAM_DESCRIPTION_MAX_LENGTH,
    TEAM_KEY_PATTERN,
    TEAM_NAME_MAX_LENGTH,
    Team,
    TeamMember,
    TeamRoleGrant,
)

TeamName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TEAM_NAME_MAX_LENGTH)
]
TeamDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=TEAM_DESCRIPTION_MAX_LENGTH)
]


class CreateTeamRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[str, StringConstraints(pattern=TEAM_KEY_PATTERN)] = Field(
        description="Stable identifier, unique in the workspace; lowercase, digits, hyphens.",
        examples=["payments-sre"],
    )
    name: TeamName = Field(examples=["Payments SRE"])
    description: TeamDescription | None = Field(default=None)


class UpdateTeamRequest(BaseModel):
    """Partial update. The key never changes. Send `description: null` to clear it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: TeamName | None = None
    description: TeamDescription | None = None


class TeamView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    key: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_team(cls, team: Team) -> "TeamView":
        return cls(
            id=team.id,
            workspace_id=team.workspace_id,
            key=team.key,
            name=team.name,
            description=team.description,
            created_at=team.created_at,
            updated_at=team.updated_at,
        )


class TeamMemberView(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: uuid.UUID
    added_by_user_id: uuid.UUID
    added_at: datetime

    @classmethod
    def from_member(cls, member: TeamMember) -> "TeamMemberView":
        return cls(
            user_id=member.user_id,
            added_by_user_id=member.added_by_user_id,
            added_at=member.created_at,
        )


class TeamRoleGrantView(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: WorkspaceRole
    granted_by_user_id: uuid.UUID
    granted_at: datetime

    @classmethod
    def from_grant(cls, grant: TeamRoleGrant) -> "TeamRoleGrantView":
        return cls(
            role=WorkspaceRole(grant.role),
            granted_by_user_id=grant.granted_by_user_id,
            granted_at=grant.created_at,
        )
