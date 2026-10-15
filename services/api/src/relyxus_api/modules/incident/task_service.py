"""Live incident tasks (MPS-11.14-11.22).

Tasks follow their incident: they are only reachable through an incident visible in the
open workspace (MPS-11.22), and tasks of a closed, cancelled or merged incident are frozen.
Owners must be workspace members. Every change is audited in the same transaction.

Not yet: dependencies and links (11.17-11.18), overdue alerts (11.16), timeline events
(11.20), and converting open tasks to follow-ups at resolution (11.21).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.service import WorkspaceAccess, WorkspaceAccessService
from relyxus_api.modules.audit.model import ActorType, AuditOutcome
from relyxus_api.modules.audit.service import AuditService, NewAuditEvent
from relyxus_api.modules.incident.lifecycle import TERMINAL_LIFECYCLE_STATES, IncidentLifecycleState
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.service import IncidentNotFoundError
from relyxus_api.modules.incident.task_model import (
    FINAL_TASK_STATUSES,
    IncidentTask,
    TaskPriority,
    TaskSource,
    TaskStatus,
)
from relyxus_api.modules.incident.task_repository import IncidentTaskRepository
from relyxus_api.modules.incident.update_service import IncidentNotEditableError
from relyxus_api.shared.errors.app_errors import ConflictError, NotFoundError, ValidationFailedError
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.pagination import InvalidCursorError, Page, PageRequest, build_page
from relyxus_api.shared.http.preconditions import assert_if_match
from relyxus_api.shared.observability.correlation import get_correlation_id
from relyxus_api.shared.utils.ids import new_uuid7

TASK_TARGET_TYPE = "incident_task"
TASK_CREATED_ACTION = "incident.task_created"
TASK_UPDATED_ACTION = "incident.task_updated"


class TaskNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_TASK_NOT_FOUND"


class TaskNotEditableError(ConflictError):
    code: ClassVar[str] = "INCIDENT_TASK_NOT_EDITABLE"


class TaskOwnerNotMemberError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_TASK_OWNER_NOT_MEMBER"


class TaskCancellationReasonRequiredError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_TASK_REASON_REQUIRED"


class NoTaskChangesError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_TASK_NO_CHANGES"


@dataclass(frozen=True, slots=True)
class NewTask:
    title: str
    priority: TaskPriority
    owner_user_id: uuid.UUID | None
    due_at: datetime | None


@dataclass(frozen=True, slots=True)
class TaskChanges:
    """`changed_fields` says which fields the caller sent, so null can clear owner or due."""

    changed_fields: frozenset[str]
    title: str | None = None
    priority: TaskPriority | None = None
    owner_user_id: uuid.UUID | None = None
    due_at: datetime | None = None
    status: TaskStatus | None = None
    reason: str | None = None
    if_match: str | None = None


class IncidentTaskService:
    def __init__(
        self,
        tasks: IncidentTaskRepository | None = None,
        incidents: IncidentRepository | None = None,
        audit: AuditService | None = None,
        access: WorkspaceAccessService | None = None,
    ) -> None:
        self._tasks = tasks or IncidentTaskRepository()
        self._incidents = incidents or IncidentRepository()
        self._audit = audit or AuditService()
        self._access = access or WorkspaceAccessService(AccessRepository())

    async def create(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        new_task: NewTask,
    ) -> IncidentTask:
        await self._require_open_incident(session, access, incident_id)
        await self._require_member(session, access, new_task.owner_user_id)
        task = await self._tasks.save(
            session,
            IncidentTask(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                incident_id=incident_id,
                title=new_task.title,
                owner_user_id=new_task.owner_user_id,
                priority=new_task.priority.value,
                status=TaskStatus.OPEN.value,
                due_at=new_task.due_at,
                source=TaskSource.MANUAL.value,
                created_by_user_id=access.user_id,
            ),
        )
        await self._record(session, access, task, TASK_CREATED_ACTION, None, _snapshot(task))
        return task

    async def list(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        page_request: PageRequest,
    ) -> Page[IncidentTask]:
        incident = await self._incidents.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        fetched = await self._tasks.list_for_incident(
            session, incident_id, _decode_cursor(page_request), page_request.limit + 1
        )
        return build_page(fetched, page_request, lambda task: (str(task.id),))

    async def update(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        task_id: uuid.UUID,
        changes: TaskChanges,
    ) -> IncidentTask:
        await self._require_open_incident(session, access, incident_id)
        task = await self._tasks.lock(session, incident_id, task_id)
        if task is None:
            raise TaskNotFoundError("No task with this ID exists on this incident.")
        assert_if_match(format_weak_etag(task.id, task.updated_at), changes.if_match)
        if TaskStatus(task.status) in FINAL_TASK_STATUSES:
            raise TaskNotEditableError(f"A {task.status} task can no longer be changed.")
        if "owner_user_id" in changes.changed_fields:
            await self._require_member(session, access, changes.owner_user_id)

        before = _snapshot(task)
        self._apply(task, changes, access.user_id)
        after = _snapshot(task)
        changed = {key for key in after if after[key] != before[key]}
        if not changed:
            raise NoTaskChangesError("The request does not change the task.")
        task = await self._tasks.save(session, task)
        await self._record(
            session,
            access,
            task,
            TASK_UPDATED_ACTION,
            {key: before[key] for key in sorted(changed)},
            {key: after[key] for key in sorted(changed)},
        )
        return task

    @staticmethod
    def _apply(task: IncidentTask, changes: TaskChanges, actor_id: uuid.UUID) -> None:
        fields = changes.changed_fields
        if "title" in fields and changes.title is not None:
            task.title = changes.title
        if "priority" in fields and changes.priority is not None:
            task.priority = changes.priority.value
        if "owner_user_id" in fields:
            task.owner_user_id = changes.owner_user_id
        if "due_at" in fields:
            task.due_at = changes.due_at
        if changes.status is None or changes.status.value == task.status:
            return
        if changes.status is TaskStatus.CANCELLED:
            if not changes.reason:
                raise TaskCancellationReasonRequiredError("A reason is required to cancel a task.")
            task.cancellation_reason = changes.reason
        if changes.status is TaskStatus.DONE:
            task.completed_at = datetime.now(UTC)
            task.completed_by_user_id = actor_id
        task.status = changes.status.value

    async def _require_open_incident(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> None:
        incident = await self._incidents.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        if IncidentLifecycleState(incident.lifecycle_state) in TERMINAL_LIFECYCLE_STATES:
            raise IncidentNotEditableError(
                f"Tasks of a {incident.lifecycle_state} incident can no longer be changed."
            )

    async def _require_member(
        self, session: AsyncSession, access: WorkspaceAccess, user_id: uuid.UUID | None
    ) -> None:
        if user_id is not None and not await self._access.is_workspace_member(
            session, user_id, access.workspace_id
        ):
            raise TaskOwnerNotMemberError("The task owner must be a member of this workspace.")

    async def _record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        task: IncidentTask,
        action: str,
        before: dict[str, object] | None,
        after: dict[str, object],
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
                target_type=TASK_TARGET_TYPE,
                target_id=str(task.id),
                outcome=AuditOutcome.SUCCEEDED,
                before_state=before,
                after_state=after,
                correlation_id=get_correlation_id(),
            ),
        )


def _snapshot(task: IncidentTask) -> dict[str, object]:
    """Audit-safe view of the task: strings, integers and nulls only (canonical JSON)."""
    return {
        "incident_id": str(task.incident_id),
        "title": task.title,
        "priority": task.priority,
        "status": task.status,
        "owner_user_id": None if task.owner_user_id is None else str(task.owner_user_id),
        "due_at": None if task.due_at is None else task.due_at.isoformat(),
        "cancellation_reason": task.cancellation_reason,
    }


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
