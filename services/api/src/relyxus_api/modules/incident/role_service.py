"""Assign and unassign incident roles (MPS-11.04; MPS-14.06 the commander assigns roles).

Rules: only an incident commander or owner may change roles; the assignee must be a member
of the workspace; roles of a closed, cancelled or merged incident are frozen. Every change
is written to the audit chain in the same transaction.

Not yet: the commander handoff package and its acknowledgement (MPS-11.23-11.24).
"""

import uuid
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.role_requirements import InsufficientWorkspaceRoleError
from relyxus_api.modules.access.service import WorkspaceAccess, WorkspaceAccessService
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.lifecycle import TERMINAL_LIFECYCLE_STATES, IncidentLifecycleState
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.role_model import IncidentRole, IncidentRoleAssignment
from relyxus_api.modules.incident.role_repository import IncidentRoleRepository
from relyxus_api.modules.incident.service import INCIDENT_TARGET_TYPE, IncidentNotFoundError
from relyxus_api.modules.incident.update_service import IncidentNotEditableError
from relyxus_api.shared.errors.app_errors import ValidationFailedError
from relyxus_api.shared.utils.ids import new_uuid7

ROLE_ASSIGNED_ACTION = "incident.role_assigned"
ROLE_UNASSIGNED_ACTION = "incident.role_unassigned"
_ROLE_MANAGERS = frozenset({WorkspaceRole.INCIDENT_COMMANDER, WorkspaceRole.OWNER})


class AssigneeNotWorkspaceMemberError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_ROLE_ASSIGNEE_NOT_MEMBER"


class IncidentRoleService:
    def __init__(
        self,
        incidents: IncidentRepository | None = None,
        activity: IncidentActivityRecorder | None = None,
        access: WorkspaceAccessService | None = None,
        roles: IncidentRoleRepository | None = None,
    ) -> None:
        self._incidents = incidents or IncidentRepository()
        self._roles = roles or IncidentRoleRepository()
        self._activity = activity or IncidentActivityRecorder()
        self._access = access or WorkspaceAccessService(AccessRepository())

    async def list_roles(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> list[IncidentRoleAssignment]:
        await self._require_incident(session, access, incident_id, is_locking=False)
        return await self._roles.list_for_incident(session, incident_id)

    async def assign(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        role: IncidentRole,
        user_id: uuid.UUID,
    ) -> IncidentRoleAssignment:
        self._require_role_manager(access)
        await self._require_incident(session, access, incident_id, is_locking=True)
        if not await self._access.is_workspace_member(session, user_id, access.workspace_id):
            raise AssigneeNotWorkspaceMemberError(
                "The assignee must be a member of this workspace."
            )
        current = await self._roles.find(session, incident_id, role.value)
        if current is not None and current.user_id == user_id:
            return current
        before: dict[str, object] | None = (
            None if current is None else {"role": role.value, "user_id": str(current.user_id)}
        )
        if current is None:
            current = IncidentRoleAssignment(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                incident_id=incident_id,
                role=role.value,
                user_id=user_id,
                assigned_by_user_id=access.user_id,
            )
        else:
            current.user_id = user_id
            current.assigned_by_user_id = access.user_id
        current = await self._roles.save(session, current)
        await self._record(
            session, access, incident_id, ROLE_ASSIGNED_ACTION, before,
            {"role": role.value, "user_id": str(user_id)},
        )  # fmt: skip
        return current

    async def unassign(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        role: IncidentRole,
    ) -> None:
        """Idempotent: removing a role nobody holds succeeds without an audit entry."""
        self._require_role_manager(access)
        await self._require_incident(session, access, incident_id, is_locking=True)
        current = await self._roles.find(session, incident_id, role.value)
        if current is None:
            return
        before: dict[str, object] = {"role": role.value, "user_id": str(current.user_id)}
        await self._roles.remove(session, current.id)
        await self._record(session, access, incident_id, ROLE_UNASSIGNED_ACTION, before, None)

    def _require_role_manager(self, access: WorkspaceAccess) -> None:
        if not _ROLE_MANAGERS.intersection(access.roles):
            raise InsufficientWorkspaceRoleError(
                "Only an incident commander or owner can change incident roles."
            )

    async def _require_incident(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        *,
        is_locking: bool,
    ) -> None:
        if is_locking:
            incident = await self._incidents.lock_in_workspace(
                session, access.workspace_id, incident_id
            )
        else:
            incident = await self._incidents.find_in_workspace(
                session, access.workspace_id, incident_id
            )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        if (
            is_locking
            and IncidentLifecycleState(incident.lifecycle_state) in TERMINAL_LIFECYCLE_STATES
        ):
            raise IncidentNotEditableError(
                f"Roles of a {incident.lifecycle_state} incident can no longer be changed."
            )

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
