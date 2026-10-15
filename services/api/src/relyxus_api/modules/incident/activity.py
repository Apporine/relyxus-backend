"""Record one incident change in both the audit chain and the incident timeline.

Every incident service records its changes through this recorder, so an audited change
always appears on the timeline (MPS-11.20, MPS-8A.33) and neither can commit without the
other: both are written in the caller's transaction.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.audit.model import ActorType, AuditOutcome
from relyxus_api.modules.audit.service import AuditService, NewAuditEvent
from relyxus_api.modules.incident.timeline_model import IncidentTimelineEvent
from relyxus_api.modules.incident.timeline_repository import IncidentTimelineRepository
from relyxus_api.shared.observability.correlation import get_correlation_id
from relyxus_api.shared.utils.ids import new_uuid7


@dataclass(frozen=True, slots=True)
class IncidentActivity:
    """`subject_*` names what changed: the incident itself, one of its tasks, and so on.

    `also_on_incident_ids` puts the same event on other incidents' timelines too (a link
    shows on both ends); the audit chain still gets one entry.
    """

    incident_id: uuid.UUID
    action: str
    subject_type: str
    subject_id: uuid.UUID
    before: dict[str, object] | None
    after: dict[str, object] | None
    also_on_incident_ids: tuple[uuid.UUID, ...] = ()


class IncidentActivityRecorder:
    def __init__(
        self,
        audit: AuditService | None = None,
        timeline: IncidentTimelineRepository | None = None,
    ) -> None:
        self._audit = audit or AuditService()
        self._timeline = timeline or IncidentTimelineRepository()

    async def record(
        self, session: AsyncSession, access: WorkspaceAccess, activity: IncidentActivity
    ) -> IncidentTimelineEvent:
        await self._audit.append(
            session,
            NewAuditEvent(
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                actor_type=ActorType.USER,
                actor_user_id=access.user_id,
                effective_user_id=None,
                action=activity.action,
                target_type=activity.subject_type,
                target_id=str(activity.subject_id),
                outcome=AuditOutcome.SUCCEEDED,
                before_state=activity.before,
                after_state=activity.after,
                correlation_id=get_correlation_id(),
            ),
        )
        events = [
            await self._timeline.append(session, _timeline_event(access, activity, incident_id))
            for incident_id in (activity.incident_id, *activity.also_on_incident_ids)
        ]
        return events[0]


def _timeline_event(
    access: WorkspaceAccess, activity: IncidentActivity, incident_id: uuid.UUID
) -> IncidentTimelineEvent:
    return IncidentTimelineEvent(
        id=new_uuid7(),
        organization_id=access.organization_id,
        workspace_id=access.workspace_id,
        incident_id=incident_id,
        kind=activity.action,
        actor_user_id=access.user_id,
        subject_type=activity.subject_type,
        subject_id=activity.subject_id,
        before_state=activity.before,
        after_state=activity.after,
    )
