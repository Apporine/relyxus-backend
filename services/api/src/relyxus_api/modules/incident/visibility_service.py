"""Change who can see an incident (MPS-8A.23, MPS-20.30).

Workspace owners and incident commanders who can see the incident change its visibility
mode and manage its access grants (register Q-42). Grants name exactly one workspace
member, team of the workspace or workspace role, always with a reason and optionally an
expiry in the future. When an incident stops being visible to the whole workspace, the
person making the change keeps access through a person grant, so nobody locks themselves
out. Every change is audited and on the timeline.

Not yet: notifications, search, webhooks, exports, analytics and AI retrieval honouring
restriction (MPS-8A.24-8A.26; Ph3 full enforcement), export lock and retention hold for
confidential incidents, database-level (RLS) enforcement as defence in depth.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.role_requirements import InsufficientWorkspaceRoleError
from relyxus_api.modules.access.service import WorkspaceAccess, WorkspaceAccessService
from relyxus_api.modules.incident.access_grant_model import (
    MAX_ACCESS_GRANTS,
    IncidentAccessGrant,
)
from relyxus_api.modules.incident.access_grant_repository import AccessGrantRepository
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.lifecycle import TERMINAL_LIFECYCLE_STATES, IncidentLifecycleState
from relyxus_api.modules.incident.model import Incident, IncidentVisibility
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.service import INCIDENT_TARGET_TYPE, IncidentNotFoundError
from relyxus_api.modules.incident.update_service import IncidentNotEditableError
from relyxus_api.modules.team.repository import TeamRepository
from relyxus_api.shared.errors.app_errors import NotFoundError, ValidationFailedError
from relyxus_api.shared.utils.ids import new_uuid7

VISIBILITY_CHANGED_ACTION = "incident.visibility_changed"
ACCESS_GRANTED_ACTION = "incident.access_granted"
ACCESS_REVOKED_ACTION = "incident.access_revoked"
_VISIBILITY_MANAGERS = frozenset({WorkspaceRole.OWNER, WorkspaceRole.INCIDENT_COMMANDER})
SELF_GRANT_REASON = "Kept access when changing the incident's visibility."


class AccessGrantNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_ACCESS_GRANT_NOT_FOUND"


class InvalidAccessGrantError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_ACCESS_GRANT_INVALID"


class NoVisibilityChangeError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_VISIBILITY_UNCHANGED"


@dataclass(frozen=True, slots=True)
class NewAccessGrant:
    """Exactly one of user_id, team_id and role is set (checked by the schema)."""

    user_id: uuid.UUID | None
    team_id: uuid.UUID | None
    role: WorkspaceRole | None
    reason: str
    expires_at: datetime | None


class IncidentVisibilityService:
    def __init__(
        self,
        incidents: IncidentRepository | None = None,
        grants: AccessGrantRepository | None = None,
        teams: TeamRepository | None = None,
        access: WorkspaceAccessService | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._incidents = incidents or IncidentRepository()
        self._grants = grants or AccessGrantRepository()
        self._teams = teams or TeamRepository()
        self._access = access or WorkspaceAccessService(AccessRepository())
        self._activity = activity or IncidentActivityRecorder()

    async def change_visibility(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        visibility: IncidentVisibility,
        reason: str,
    ) -> Incident:
        incident = await self._lock_managed_incident(session, access, incident_id)
        current = IncidentVisibility(incident.visibility)
        if current is visibility:
            raise NoVisibilityChangeError(f"The incident is already {visibility.value}.")
        if visibility is not IncidentVisibility.WORKSPACE:
            await self._keep_own_access(session, access, incident)
        incident.visibility = visibility.value
        incident = await self._incidents.save(session, incident)
        await self._record(
            session,
            access,
            incident.id,
            VISIBILITY_CHANGED_ACTION,
            {"visibility": current.value},
            {"visibility": visibility.value, "reason": reason},
        )
        return incident

    async def list_grants(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> list[IncidentAccessGrant]:
        incident = await self._incidents.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        return await self._grants.list_for_incident(session, incident_id)

    async def grant(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        new_grant: NewAccessGrant,
    ) -> IncidentAccessGrant:
        incident = await self._lock_managed_incident(session, access, incident_id)
        await self._validate(session, access, new_grant)
        if await self._grants.count_for_incident(session, incident.id) >= MAX_ACCESS_GRANTS:
            raise InvalidAccessGrantError(
                f"An incident can have at most {MAX_ACCESS_GRANTS} access grants."
            )
        return await self._add(session, access, incident.id, new_grant)

    async def revoke(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        grant_id: uuid.UUID,
    ) -> None:
        incident = await self._lock_managed_incident(session, access, incident_id)
        grant = await self._grants.find(session, incident.id, grant_id)
        if grant is None:
            raise AccessGrantNotFoundError("No access grant with this ID exists on the incident.")
        await self._grants.remove(session, grant.id)
        await self._record(
            session, access, incident.id, ACCESS_REVOKED_ACTION, _grant_state(grant), None
        )

    async def _keep_own_access(
        self, session: AsyncSession, access: WorkspaceAccess, incident: Incident
    ) -> None:
        if WorkspaceRole.OWNER in access.roles or access.user_id in {
            incident.created_by_user_id,
            incident.declared_by_user_id,
        }:
            return
        if await self._grants.find_person_grant(session, incident.id, access.user_id):
            return
        await self._add(
            session,
            access,
            incident.id,
            NewAccessGrant(
                user_id=access.user_id,
                team_id=None,
                role=None,
                reason=SELF_GRANT_REASON,
                expires_at=None,
            ),
        )

    async def _add(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        new_grant: NewAccessGrant,
    ) -> IncidentAccessGrant:
        grant = await self._grants.add(
            session,
            IncidentAccessGrant(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                incident_id=incident_id,
                user_id=new_grant.user_id,
                team_id=new_grant.team_id,
                role=None if new_grant.role is None else new_grant.role.value,
                reason=new_grant.reason,
                expires_at=new_grant.expires_at,
                granted_by_user_id=access.user_id,
            ),
        )
        await self._record(
            session, access, incident_id, ACCESS_GRANTED_ACTION, None, _grant_state(grant)
        )
        return grant

    async def _validate(
        self, session: AsyncSession, access: WorkspaceAccess, new_grant: NewAccessGrant
    ) -> None:
        if new_grant.expires_at is not None and new_grant.expires_at <= datetime.now(UTC):
            raise InvalidAccessGrantError("A grant's expiry must be in the future.")
        if new_grant.user_id is not None and not await self._access.is_workspace_member(
            session, new_grant.user_id, access.workspace_id
        ):
            raise InvalidAccessGrantError("Person grants must name a member of this workspace.")
        if new_grant.team_id is not None and not await self._teams.find_in_workspace(
            session, access.workspace_id, new_grant.team_id
        ):
            raise InvalidAccessGrantError("Team grants must name a team of this workspace.")

    async def _lock_managed_incident(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> Incident:
        incident = await self._incidents.lock_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        if not _VISIBILITY_MANAGERS.intersection(access.roles):
            raise InsufficientWorkspaceRoleError(
                "Only owners and incident commanders can change who sees an incident."
            )
        if IncidentLifecycleState(incident.lifecycle_state) in TERMINAL_LIFECYCLE_STATES:
            raise IncidentNotEditableError(
                f"Visibility of a {incident.lifecycle_state} incident can no longer change."
            )
        return incident

    async def _record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        action: str,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
    ) -> None:
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=incident_id,
                action=action,
                subject_type=INCIDENT_TARGET_TYPE,
                subject_id=incident_id,
                before=before,
                after=after,
            ),
        )


def _grant_state(grant: IncidentAccessGrant) -> dict[str, object]:
    return {
        "grant_id": str(grant.id),
        "user_id": None if grant.user_id is None else str(grant.user_id),
        "team_id": None if grant.team_id is None else str(grant.team_id),
        "role": grant.role,
        "reason": grant.reason,
        "expires_at": None if grant.expires_at is None else grant.expires_at.isoformat(),
    }
