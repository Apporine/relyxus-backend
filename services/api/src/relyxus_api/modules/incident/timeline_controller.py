import uuid

from fastapi import APIRouter

from relyxus_api.modules.access.dependencies import WorkspaceSessionDependency
from relyxus_api.modules.incident.timeline_schema import TimelineEventView
from relyxus_api.modules.incident.timeline_service import IncidentTimelineService
from relyxus_api.shared.http.envelope import ListEnvelope, wrap_page
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

TIMELINE_TAG = "incident-timeline"

router = APIRouter(prefix="/api/v1", tags=[TIMELINE_TAG])


@router.get(
    "/incidents/{incident_id}/timeline",
    summary="Read an incident's timeline",
    description=(
        "Every change to the incident, its roles and its tasks, oldest first. Events are "
        "written in the same transaction as the change and are never edited or removed. "
        "Cursor-paginated; no total. Visibility follows the incident."
    ),
    response_model=ListEnvelope[TimelineEventView],
)
async def list_timeline(
    incident_id: uuid.UUID,
    workspace: WorkspaceSessionDependency,
    page_request: PageRequestDependency,
) -> ListEnvelope[TimelineEventView]:
    page = await IncidentTimelineService().list(
        workspace.session, workspace.access, incident_id, page_request
    )
    views = [TimelineEventView.from_event(event) for event in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))
