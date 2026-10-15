"""Move an unfinished live task to a follow-up at resolution (MPS-11.21, MPS-20.32).

Only while the incident is resolved: live tasks freeze once it is closed. The task keeps
its history and ends as cancelled with a fixed reason; the new follow-up copies its title,
owner and due date and points back at it (`source_task_id`, unique, so a task converts at
most once). Both changes are audited and on the timeline in one transaction.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.follow_up_model import IncidentFollowUp
from relyxus_api.modules.incident.follow_up_service import IncidentFollowUpService, NewFollowUp
from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.task_model import FINAL_TASK_STATUSES, TaskStatus
from relyxus_api.modules.incident.task_repository import IncidentTaskRepository
from relyxus_api.modules.incident.task_service import (
    TASK_TARGET_TYPE,
    TASK_UPDATED_ACTION,
    TaskNotEditableError,
    TaskNotFoundError,
)
from relyxus_api.modules.incident.update_service import IncidentNotEditableError

MOVED_TO_FOLLOW_UP_REASON = "Moved to a follow-up at resolution."


class IncidentTaskConversionService:
    def __init__(
        self,
        tasks: IncidentTaskRepository | None = None,
        follow_ups: IncidentFollowUpService | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._tasks = tasks or IncidentTaskRepository()
        self._follow_ups = follow_ups or IncidentFollowUpService()
        self._activity = activity or IncidentActivityRecorder()

    async def convert(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        task_id: uuid.UUID,
        is_mandatory: bool | None,
    ) -> IncidentFollowUp:
        incident = await self._follow_ups.require_post_incident(session, access, incident_id)
        if incident.lifecycle_state != IncidentLifecycleState.RESOLVED.value:
            raise IncidentNotEditableError(
                f"Tasks of a {incident.lifecycle_state} incident can no longer be changed."
            )
        task = await self._tasks.lock(session, incident_id, task_id)
        if task is None:
            raise TaskNotFoundError("No task with this ID exists on this incident.")
        if TaskStatus(task.status) in FINAL_TASK_STATUSES:
            raise TaskNotEditableError(f"A {task.status} task can no longer be changed.")

        before_status = task.status
        task.status = TaskStatus.CANCELLED.value
        task.cancellation_reason = MOVED_TO_FOLLOW_UP_REASON
        task = await self._tasks.save(session, task)
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=incident_id,
                action=TASK_UPDATED_ACTION,
                subject_type=TASK_TARGET_TYPE,
                subject_id=task.id,
                before={"status": before_status, "cancellation_reason": None},
                after={"status": task.status, "cancellation_reason": task.cancellation_reason},
            ),
        )
        return await self._follow_ups.add(
            session,
            access,
            incident,
            NewFollowUp(
                title=task.title,
                owner_user_id=task.owner_user_id,
                due_at=task.due_at,
                is_mandatory=is_mandatory,
                source_task_id=task.id,
            ),
        )
