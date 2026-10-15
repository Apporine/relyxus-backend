"""Teams and team membership (MPS-14.01, MPS-14.02, MPS-20.05).

Owners and admins manage teams ("Admin — users, teams, connectors, settings", MPS-14.02);
every workspace member can read them. A team's key is its stable identifier and never
changes (MPS-14A configuration with stable IDs); name and description can. Members must
already be members of the workspace. Every change is written to the workspace audit chain
in the same transaction.

Not yet: team role grants (Q-18, next change), on-call schedules and escalation policies
(MPS-20.05, MPS-11.07), archiving teams.
"""

import uuid
from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.service import WorkspaceAccess, WorkspaceAccessService
from relyxus_api.modules.audit.model import ActorType, AuditOutcome
from relyxus_api.modules.audit.service import AuditService, NewAuditEvent
from relyxus_api.modules.team.model import Team, TeamMember
from relyxus_api.modules.team.repository import TeamRepository
from relyxus_api.shared.errors.app_errors import ConflictError, NotFoundError, ValidationFailedError
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.id_cursor import decode_id_cursor
from relyxus_api.shared.http.pagination import Page, PageRequest, build_page
from relyxus_api.shared.http.preconditions import assert_if_match
from relyxus_api.shared.observability.correlation import get_correlation_id
from relyxus_api.shared.utils.ids import new_uuid7

TEAM_TARGET_TYPE = "team"
TEAM_CREATED_ACTION = "team.created"
TEAM_UPDATED_ACTION = "team.updated"
TEAM_MEMBER_ADDED_ACTION = "team.member_added"
TEAM_MEMBER_REMOVED_ACTION = "team.member_removed"


class TeamNotFoundError(NotFoundError):
    code: ClassVar[str] = "TEAM_NOT_FOUND"


class TeamKeyTakenError(ConflictError):
    code: ClassVar[str] = "TEAM_KEY_TAKEN"


class TeamMemberNotFoundError(NotFoundError):
    code: ClassVar[str] = "TEAM_MEMBER_NOT_FOUND"


class TeamMemberNotWorkspaceMemberError(ValidationFailedError):
    code: ClassVar[str] = "TEAM_MEMBER_NOT_WORKSPACE_MEMBER"


class NoTeamChangesError(ValidationFailedError):
    code: ClassVar[str] = "TEAM_NO_CHANGES"


@dataclass(frozen=True, slots=True)
class NewTeam:
    key: str
    name: str
    description: str | None


@dataclass(frozen=True, slots=True)
class TeamChanges:
    """`changed_fields` says which fields were sent, so null can clear the description."""

    changed_fields: frozenset[str]
    name: str | None = None
    description: str | None = None
    if_match: str | None = None


class TeamService:
    def __init__(
        self,
        repository: TeamRepository | None = None,
        audit: AuditService | None = None,
        access: WorkspaceAccessService | None = None,
    ) -> None:
        self._repository = repository or TeamRepository()
        self._audit = audit or AuditService()
        self._access = access or WorkspaceAccessService(AccessRepository())

    async def create(
        self, session: AsyncSession, access: WorkspaceAccess, new_team: NewTeam
    ) -> Team:
        if await self._repository.find_by_key(session, access.workspace_id, new_team.key):
            raise TeamKeyTakenError(f"A team with the key '{new_team.key}' already exists.")
        team = await self._repository.save_team(
            session,
            Team(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                key=new_team.key,
                name=new_team.name,
                description=new_team.description,
            ),
        )
        await self._record(session, access, team.id, TEAM_CREATED_ACTION, None, _snapshot(team))
        return team

    async def get(self, session: AsyncSession, access: WorkspaceAccess, team_id: uuid.UUID) -> Team:
        team = await self._repository.find_in_workspace(session, access.workspace_id, team_id)
        if team is None:
            raise TeamNotFoundError("No team with this ID exists in this workspace.")
        return team

    async def list(
        self, session: AsyncSession, access: WorkspaceAccess, page_request: PageRequest
    ) -> Page[Team]:
        fetched = await self._repository.list_in_workspace(
            session, access.workspace_id, decode_id_cursor(page_request), page_request.limit + 1
        )
        return build_page(fetched, page_request, lambda team: (str(team.id),))

    async def update(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        team_id: uuid.UUID,
        changes: TeamChanges,
    ) -> Team:
        team = await self._lock(session, access, team_id)
        assert_if_match(format_weak_etag(team.id, team.updated_at), changes.if_match)
        before = _snapshot(team)
        if "name" in changes.changed_fields and changes.name is not None:
            team.name = changes.name
        if "description" in changes.changed_fields:
            team.description = changes.description
        after = _snapshot(team)
        changed = sorted(key for key in after if after[key] != before[key])
        if not changed:
            raise NoTeamChangesError("The request does not change the team.")
        team = await self._repository.save_team(session, team)
        await self._record(
            session,
            access,
            team.id,
            TEAM_UPDATED_ACTION,
            {key: before[key] for key in changed},
            {key: after[key] for key in changed},
        )
        return team

    async def list_members(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        team_id: uuid.UUID,
        page_request: PageRequest,
    ) -> Page[TeamMember]:
        team = await self.get(session, access, team_id)
        fetched = await self._repository.list_members(
            session, team.id, decode_id_cursor(page_request), page_request.limit + 1
        )
        return build_page(fetched, page_request, lambda member: (str(member.id),))

    async def add_member(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> TeamMember:
        """Idempotent: adding a current member returns the existing membership."""
        team = await self._lock(session, access, team_id)
        existing = await self._repository.find_member(session, team.id, user_id)
        if existing is not None:
            return existing
        if not await self._access.is_workspace_member(session, user_id, access.workspace_id):
            raise TeamMemberNotWorkspaceMemberError(
                "Team members must be members of this workspace."
            )
        member = await self._repository.save_member(
            session,
            TeamMember(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                team_id=team.id,
                user_id=user_id,
                added_by_user_id=access.user_id,
            ),
        )
        await self._record(
            session, access, team.id, TEAM_MEMBER_ADDED_ACTION, None, {"user_id": str(user_id)}
        )
        return member

    async def remove_member(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        team = await self._lock(session, access, team_id)
        member = await self._repository.find_member(session, team.id, user_id)
        if member is None:
            raise TeamMemberNotFoundError("This person is not a member of the team.")
        await self._repository.remove_member(session, member.id)
        await self._record(
            session, access, team.id, TEAM_MEMBER_REMOVED_ACTION, {"user_id": str(user_id)}, None
        )

    async def _lock(
        self, session: AsyncSession, access: WorkspaceAccess, team_id: uuid.UUID
    ) -> Team:
        team = await self._repository.find_in_workspace(
            session, access.workspace_id, team_id, is_locking=True
        )
        if team is None:
            raise TeamNotFoundError("No team with this ID exists in this workspace.")
        return team

    async def _record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        team_id: uuid.UUID,
        action: str,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
    ) -> None:
        await self._audit.append(
            session,
            NewAuditEvent(
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                actor_type=ActorType.USER,
                actor_user_id=access.user_id,
                effective_user_id=None,
                action=action,
                target_type=TEAM_TARGET_TYPE,
                target_id=str(team_id),
                outcome=AuditOutcome.SUCCEEDED,
                before_state=before,
                after_state=after,
                correlation_id=get_correlation_id(),
            ),
        )


def _snapshot(team: Team) -> dict[str, object]:
    return {"key": team.key, "name": team.name, "description": team.description}
