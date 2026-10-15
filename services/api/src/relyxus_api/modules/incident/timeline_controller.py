import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WorkspaceSessionDependency
from relyxus_api.modules.access.role_requirements import IncidentWriteWorkspaceDependency
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.incident.timeline_schema import AddNoteRequest, TimelineEventView
from relyxus_api.modules.incident.timeline_service import IncidentTimelineService
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

TIMELINE_TAG = "incident-timeline"
CREATED_STATUS = 201

router = APIRouter(prefix="/api/v1", tags=[TIMELINE_TAG])


@router.get(
    "/incidents/{incident_id}/timeline",
    summary="Read an incident's timeline",
    description=(
        "Every change to the incident, its roles and its tasks, and every note, oldest first. "
        "Events are written in the same transaction as the change and are never edited or "
        "removed. Cursor-paginated; no total. Visibility follows the incident."
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


@router.post(
    "/incidents/{incident_id}/timeline/notes",
    summary="Add a note to an incident's timeline",
    description=(
        "Records a human note (`incident.note_added`) on the timeline and in the audit chain. "
        "Notes cannot be edited or removed; post a new note to correct one. Not allowed once "
        f"the incident is closed, cancelled or merged. Requires `{IDEMPOTENCY_HEADER}` and an "
        "incident-writing role."
    ),
    response_model=SuccessEnvelope[TimelineEventView],
    status_code=CREATED_STATUS,
)
async def add_note(
    request: Request,
    incident_id: uuid.UUID,
    workspace: IncidentWriteWorkspaceDependency,
    body: AddNoteRequest,
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER)],
) -> Response:
    idempotency = IdempotencyService()
    reservation = await idempotency.begin(
        workspace.session,
        organization_id=workspace.access.organization_id,
        idempotency_key=idempotency_key,
        method=request.method,
        path=request.url.path,
        payload=body.model_dump(mode="json"),
    )
    if isinstance(reservation, IdempotencyReplay):
        return JSONResponse(status_code=reservation.status_code, content=reservation.body)

    event = await IncidentTimelineService().add_note(
        workspace.session, workspace.access, incident_id, body.text
    )
    payload = wrap_success(TimelineEventView.from_event(event)).model_dump(mode="json")
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=CREATED_STATUS, body=payload
    )
    return JSONResponse(status_code=CREATED_STATUS, content=payload)
