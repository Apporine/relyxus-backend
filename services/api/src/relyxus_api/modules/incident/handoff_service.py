"""Hand an incident role from its holder to another member (MPS-11.23, 11.24, 20.33).

Request: the current holder, an incident commander or an owner proposes a handoff to
another member. Relyxus snapshots the handoff package at that moment: the incident
summary, current role holders and unfinished tasks. One pending handoff per role.

Accept: only the incoming person can accept. That acknowledgement moves the role and
records outgoing, incoming and time on the timeline. A handoff whose outgoing person no
longer holds the role is stale and cannot be accepted.

Cancel: the requester, either person or a role manager may cancel a pending handoff;
the incoming person cancelling it is how they decline.

Not yet (their records do not exist): pending approvals, active clocks and deadlines,
risks and unknowns and the next update time in the package (MPS-11.23); acknowledging or
deferring approvals and clocks due within an hour (MPS-11.24). The package lists these
sections under `unavailable_sections` so readers know they are missing, not empty.
"""

import uuid
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.role_requirements import InsufficientWorkspaceRoleError
from relyxus_api.modules.access.service import WorkspaceAccess, WorkspaceAccessService
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.handoff_model import HandoffState, IncidentRoleHandoff
from relyxus_api.modules.incident.handoff_repository import IncidentHandoffRepository
from relyxus_api.modules.incident.lifecycle import TERMINAL_LIFECYCLE_STATES, IncidentLifecycleState
from relyxus_api.modules.incident.model import Incident
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.role_model import IncidentRole
from relyxus_api.modules.incident.role_repository import IncidentRoleRepository
from relyxus_api.modules.incident.role_service import AssigneeNotWorkspaceMemberError
from relyxus_api.modules.incident.service import IncidentNotFoundError
from relyxus_api.modules.incident.task_model import TaskStatus
from relyxus_api.modules.incident.task_repository import IncidentTaskRepository
from relyxus_api.modules.incident.update_service import IncidentNotEditableError
from relyxus_api.shared.errors.app_errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from relyxus_api.shared.http.pagination import InvalidCursorError, Page, PageRequest, build_page
from relyxus_api.shared.utils.ids import new_uuid7

HANDOFF_SUBJECT_TYPE = "incident_role_handoff"
HANDOFF_REQUESTED_ACTION = "incident.handoff_requested"
HANDOFF_ACCEPTED_ACTION = "incident.handoff_accepted"
HANDOFF_CANCELLED_ACTION = "incident.handoff_cancelled"
PACKAGE_TASK_LIMIT = 200
_ROLE_MANAGERS = frozenset({WorkspaceRole.INCIDENT_COMMANDER, WorkspaceRole.OWNER})
_UNFINISHED_TASK_STATUSES = [TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]
_UNAVAILABLE_SECTIONS = [
    "pending_approvals",
    "active_clocks",
    "risks_and_unknowns",
    "next_update_at",
]


class HandoffNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_HANDOFF_NOT_FOUND"


class NoCurrentHolderError(ConflictError):
    code: ClassVar[str] = "INCIDENT_HANDOFF_NO_CURRENT_HOLDER"


class HandoffAlreadyPendingError(ConflictError):
    code: ClassVar[str] = "INCIDENT_HANDOFF_ALREADY_PENDING"


class HandoffNotPendingError(ConflictError):
    code: ClassVar[str] = "INCIDENT_HANDOFF_NOT_PENDING"


class HandoffStaleError(ConflictError):
    code: ClassVar[str] = "INCIDENT_HANDOFF_STALE"


class HandoffToCurrentHolderError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_HANDOFF_SAME_PERSON"


class NotHandoffRecipientError(PermissionDeniedError):
    code: ClassVar[str] = "INCIDENT_HANDOFF_NOT_RECIPIENT"


class IncidentHandoffService:
    def __init__(
        self,
        handoffs: IncidentHandoffRepository | None = None,
        incidents: IncidentRepository | None = None,
        roles: IncidentRoleRepository | None = None,
        tasks: IncidentTaskRepository | None = None,
        access: WorkspaceAccessService | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._handoffs = handoffs or IncidentHandoffRepository()
        self._incidents = incidents or IncidentRepository()
        self._roles = roles or IncidentRoleRepository()
        self._tasks = tasks or IncidentTaskRepository()
        self._access = access or WorkspaceAccessService(AccessRepository())
        self._activity = activity or IncidentActivityRecorder()

    async def request(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        role: IncidentRole,
        to_user_id: uuid.UUID,
    ) -> IncidentRoleHandoff:
        incident = await self._lock_open_incident(session, access, incident_id)
        holder = await self._roles.find(session, incident_id, role.value)
        if holder is None:
            raise NoCurrentHolderError(
                f"Nobody holds the {role.value} role; assign it instead of handing it off."
            )
        if holder.user_id != access.user_id and not _ROLE_MANAGERS.intersection(access.roles):
            raise InsufficientWorkspaceRoleError(
                "Only the role holder, an incident commander or an owner can hand a role off."
            )
        if to_user_id == holder.user_id:
            raise HandoffToCurrentHolderError("The incoming person already holds this role.")
        if not await self._access.is_workspace_member(session, to_user_id, access.workspace_id):
            raise AssigneeNotWorkspaceMemberError(
                "The incoming person must be a member of this workspace."
            )
        if await self._handoffs.find_pending(session, incident_id, role.value) is not None:
            raise HandoffAlreadyPendingError(
                f"A handoff of the {role.value} role is already pending; accept or cancel it."
            )

        handoff = await self._handoffs.save(
            session,
            IncidentRoleHandoff(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                incident_id=incident_id,
                role=role.value,
                state=HandoffState.PENDING.value,
                from_user_id=holder.user_id,
                to_user_id=to_user_id,
                requested_by_user_id=access.user_id,
                package_snapshot=await self._build_package(session, incident),
            ),
        )
        await self._record(session, access, handoff, HANDOFF_REQUESTED_ACTION, None)
        return handoff

    async def accept(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        handoff_id: uuid.UUID,
    ) -> IncidentRoleHandoff:
        await self._lock_open_incident(session, access, incident_id)
        handoff = await self._lock_pending(session, incident_id, handoff_id)
        if handoff.to_user_id != access.user_id:
            raise NotHandoffRecipientError("Only the incoming person can accept a handoff.")
        holder = await self._roles.find(session, incident_id, handoff.role)
        if holder is None or holder.user_id != handoff.from_user_id:
            raise HandoffStaleError(
                "The role changed since this handoff was requested; cancel it and start again."
            )

        holder.user_id = handoff.to_user_id
        holder.assigned_by_user_id = access.user_id
        await self._roles.save(session, holder)
        handoff.state = HandoffState.ACCEPTED.value
        handoff.accepted_at = datetime.now(UTC)
        handoff = await self._handoffs.save(session, handoff)
        await self._record(
            session,
            access,
            handoff,
            HANDOFF_ACCEPTED_ACTION,
            {"role": handoff.role, "user_id": str(handoff.from_user_id)},
        )
        return handoff

    async def cancel(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        handoff_id: uuid.UUID,
    ) -> IncidentRoleHandoff:
        incident = await self._incidents.lock_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        handoff = await self._lock_pending(session, incident_id, handoff_id)
        people = {handoff.requested_by_user_id, handoff.from_user_id, handoff.to_user_id}
        if access.user_id not in people and not _ROLE_MANAGERS.intersection(access.roles):
            raise InsufficientWorkspaceRoleError(
                "Only the people in this handoff, an incident commander or an owner can cancel it."
            )
        handoff.state = HandoffState.CANCELLED.value
        handoff.cancelled_at = datetime.now(UTC)
        handoff.cancelled_by_user_id = access.user_id
        handoff = await self._handoffs.save(session, handoff)
        await self._record(session, access, handoff, HANDOFF_CANCELLED_ACTION, None)
        return handoff

    async def list(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        page_request: PageRequest,
    ) -> Page[IncidentRoleHandoff]:
        incident = await self._incidents.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        fetched = await self._handoffs.list_for_incident(
            session, incident_id, _decode_cursor(page_request), page_request.limit + 1
        )
        return build_page(fetched, page_request, lambda handoff: (str(handoff.id),))

    async def _lock_open_incident(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> Incident:
        incident = await self._incidents.lock_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        if IncidentLifecycleState(incident.lifecycle_state) in TERMINAL_LIFECYCLE_STATES:
            raise IncidentNotEditableError(
                f"Roles of a {incident.lifecycle_state} incident can no longer be handed off."
            )
        return incident

    async def _lock_pending(
        self, session: AsyncSession, incident_id: uuid.UUID, handoff_id: uuid.UUID
    ) -> IncidentRoleHandoff:
        handoff = await self._handoffs.lock(session, incident_id, handoff_id)
        if handoff is None:
            raise HandoffNotFoundError("No handoff with this ID exists on this incident.")
        if handoff.state != HandoffState.PENDING.value:
            raise HandoffNotPendingError(f"This handoff is already {handoff.state}.")
        return handoff

    async def _build_package(self, session: AsyncSession, incident: Incident) -> dict[str, object]:
        roles = await self._roles.list_for_incident(session, incident.id)
        tasks = await self._tasks.list_unfinished_for_incident(
            session,
            incident.id,
            [status.value for status in _UNFINISHED_TASK_STATUSES],
            PACKAGE_TASK_LIMIT + 1,
        )
        return {
            "captured_at": datetime.now(UTC).isoformat(),
            "incident": {
                "number": incident.number,
                "title": incident.title,
                "severity": incident.severity,
                "lifecycle_state": incident.lifecycle_state,
            },
            "roles": [
                {"role": assignment.role, "user_id": str(assignment.user_id)}
                for assignment in roles
            ],
            "open_tasks": [
                {
                    "id": str(task.id),
                    "title": task.title,
                    "status": task.status,
                    "priority": task.priority,
                    "owner_user_id": None
                    if task.owner_user_id is None
                    else str(task.owner_user_id),
                    "due_at": None
                    if task.due_at is None
                    else task.due_at.astimezone(UTC).isoformat(),
                }
                for task in tasks[:PACKAGE_TASK_LIMIT]
            ],
            "open_tasks_truncated": len(tasks) > PACKAGE_TASK_LIMIT,
            "unavailable_sections": list(_UNAVAILABLE_SECTIONS),
        }

    async def _record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        handoff: IncidentRoleHandoff,
        action: str,
        before: dict[str, object] | None,
    ) -> None:
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=handoff.incident_id,
                action=action,
                subject_type=HANDOFF_SUBJECT_TYPE,
                subject_id=handoff.id,
                before=before,
                after={
                    "role": handoff.role,
                    "state": handoff.state,
                    "from_user_id": str(handoff.from_user_id),
                    "to_user_id": str(handoff.to_user_id),
                },
            ),
        )


def _decode_cursor(page_request: PageRequest) -> uuid.UUID | None:
    if page_request.after is None:
        return None
    position = page_request.after
    if len(position) != 1 or not isinstance(position[0], str):
        raise InvalidCursorError("The cursor is not valid; restart from the first page.")
    try:
        return uuid.UUID(position[0])
    except ValueError as error:
        raise InvalidCursorError("The cursor is not valid; restart from the first page.") from error
