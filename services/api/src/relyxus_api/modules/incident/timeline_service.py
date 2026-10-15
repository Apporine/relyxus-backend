"""Read an incident's timeline and add notes to it (MPS-5.20, MPS-8A.33, MPS-11.20).

Visibility follows the incident: a timeline is only reachable through an incident visible
in the open workspace. Change events are written by `IncidentActivityRecorder` from the
service that made the change; this service only adds human notes. Notes are immutable
like every timeline event: a correction is a new note.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.lifecycle import TERMINAL_LIFECYCLE_STATES, IncidentLifecycleState
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.service import IncidentNotFoundError
from relyxus_api.modules.incident.timeline_model import IncidentTimelineEvent
from relyxus_api.modules.incident.timeline_repository import IncidentTimelineRepository
from relyxus_api.modules.incident.update_service import IncidentNotEditableError
from relyxus_api.shared.http.pagination import InvalidCursorError, Page, PageRequest, build_page
from relyxus_api.shared.utils.ids import new_uuid7

NOTE_ADDED_ACTION = "incident.note_added"
NOTE_SUBJECT_TYPE = "incident_note"


class IncidentTimelineService:
    def __init__(
        self,
        timeline: IncidentTimelineRepository | None = None,
        incidents: IncidentRepository | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._timeline = timeline or IncidentTimelineRepository()
        self._incidents = incidents or IncidentRepository()
        self._activity = activity or IncidentActivityRecorder()

    async def list(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        page_request: PageRequest,
    ) -> Page[IncidentTimelineEvent]:
        """Oldest first, so a reader follows the incident as it happened."""
        incident = await self._incidents.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        fetched = await self._timeline.list_for_incident(
            session, incident_id, _decode_cursor(page_request), page_request.limit + 1
        )
        return build_page(fetched, page_request, lambda event: (event.sequence,))

    async def add_note(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID, text: str
    ) -> IncidentTimelineEvent:
        """Notes are allowed until the incident is closed, cancelled or merged."""
        incident = await self._incidents.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        if IncidentLifecycleState(incident.lifecycle_state) in TERMINAL_LIFECYCLE_STATES:
            raise IncidentNotEditableError(
                f"Notes can no longer be added to a {incident.lifecycle_state} incident."
            )
        return await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=incident_id,
                action=NOTE_ADDED_ACTION,
                subject_type=NOTE_SUBJECT_TYPE,
                subject_id=new_uuid7(),
                before=None,
                after={"text": text},
            ),
        )


def _decode_cursor(page_request: PageRequest) -> int | None:
    if page_request.after is None:
        return None
    position = page_request.after
    if len(position) != 1 or not isinstance(position[0], int) or position[0] < 1:
        raise InvalidCursorError("The cursor is not valid; restart from the first page.")
    return position[0]
