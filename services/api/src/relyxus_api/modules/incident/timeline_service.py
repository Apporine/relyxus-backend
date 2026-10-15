"""Read an incident's timeline (MPS-5.20, MPS-8A.33, MPS-11.20).

Visibility follows the incident: a timeline is only reachable through an incident visible
in the open workspace. Events are written by `IncidentActivityRecorder`, never here.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.service import IncidentNotFoundError
from relyxus_api.modules.incident.timeline_model import IncidentTimelineEvent
from relyxus_api.modules.incident.timeline_repository import IncidentTimelineRepository
from relyxus_api.shared.http.pagination import InvalidCursorError, Page, PageRequest, build_page


class IncidentTimelineService:
    def __init__(
        self,
        timeline: IncidentTimelineRepository | None = None,
        incidents: IncidentRepository | None = None,
    ) -> None:
        self._timeline = timeline or IncidentTimelineRepository()
        self._incidents = incidents or IncidentRepository()

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


def _decode_cursor(page_request: PageRequest) -> int | None:
    if page_request.after is None:
        return None
    position = page_request.after
    if len(position) != 1 or not isinstance(position[0], int) or position[0] < 1:
        raise InvalidCursorError("The cursor is not valid; restart from the first page.")
    return position[0]
