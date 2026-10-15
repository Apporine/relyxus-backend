"""Acknowledge an incident (MPS-15.02 war room "Acknowledge"; MPS-8A.20 metric timestamp).

The first acknowledgement records who and when; it feeds time-to-acknowledge. A second
acknowledgement is refused rather than silently moving the timestamp. Only incidents that
are still being worked (triage to monitoring) can be acknowledged.

Not yet: stopping the escalation chase on acknowledgement (MPS-11.07) and syncing it to
PagerDuty or Opsgenie (MPS-11.08); paging does not exist yet.
"""

import uuid
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.model import Incident
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.service import INCIDENT_TARGET_TYPE, IncidentNotFoundError
from relyxus_api.shared.errors.app_errors import ConflictError

ACKNOWLEDGED_ACTION = "incident.acknowledged"
_ACKNOWLEDGEABLE_STATES = frozenset(
    {
        IncidentLifecycleState.TRIAGE,
        IncidentLifecycleState.INVESTIGATING,
        IncidentLifecycleState.MITIGATING,
        IncidentLifecycleState.MONITORING,
    }
)


class IncidentAlreadyAcknowledgedError(ConflictError):
    code: ClassVar[str] = "INCIDENT_ALREADY_ACKNOWLEDGED"


class IncidentNotAcknowledgeableError(ConflictError):
    code: ClassVar[str] = "INCIDENT_NOT_ACKNOWLEDGEABLE"


class IncidentAcknowledgeService:
    def __init__(
        self,
        repository: IncidentRepository | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._repository = repository or IncidentRepository()
        self._activity = activity or IncidentActivityRecorder()

    async def acknowledge(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> Incident:
        incident = await self._repository.lock_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        if incident.acknowledged_at is not None:
            raise IncidentAlreadyAcknowledgedError("This incident has already been acknowledged.")
        if IncidentLifecycleState(incident.lifecycle_state) not in _ACKNOWLEDGEABLE_STATES:
            raise IncidentNotAcknowledgeableError(
                f"A {incident.lifecycle_state} incident cannot be acknowledged."
            )

        acknowledged_at = datetime.now(UTC)
        incident.acknowledged_at = acknowledged_at
        incident.acknowledged_by_user_id = access.user_id
        incident = await self._repository.save(session, incident)
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=incident.id,
                action=ACKNOWLEDGED_ACTION,
                subject_type=INCIDENT_TARGET_TYPE,
                subject_id=incident.id,
                before=None,
                after={"acknowledged_at": acknowledged_at.isoformat()},
            ),
        )
        return incident
