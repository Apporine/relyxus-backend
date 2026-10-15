import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response, status
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WorkspaceSessionDependency
from relyxus_api.modules.access.role_requirements import IncidentWriteWorkspaceDependency
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.incident.link_schema import AddIncidentLinkRequest, IncidentLinkView
from relyxus_api.modules.incident.link_service import IncidentLinkService
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

LINKS_TAG = "incident-links"
CREATED_STATUS = 201

router = APIRouter(prefix="/api/v1", tags=[LINKS_TAG])


@router.post(
    "/incidents/{incident_id}/links",
    summary="Link this incident to another",
    description=(
        "Records that this incident is `duplicate_of`, `caused_by`, `related_to` or "
        "`recurrence_of` another incident in the same workspace (MPS-8A.31). Two incidents "
        "share at most one link of each type, in either direction. The link appears on both "
        "incidents' timelines. Not allowed once this incident is closed, cancelled or merged. "
        f"Requires `{IDEMPOTENCY_HEADER}` and an incident-writing role."
    ),
    response_model=SuccessEnvelope[IncidentLinkView],
    status_code=CREATED_STATUS,
)
async def add_incident_link(
    request: Request,
    incident_id: uuid.UUID,
    workspace: IncidentWriteWorkspaceDependency,
    body: AddIncidentLinkRequest,
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

    link = await IncidentLinkService().add(
        workspace.session, workspace.access, incident_id, body.target_incident_id, body.link_type
    )
    payload = wrap_success(IncidentLinkView.from_link(link, incident_id)).model_dump(mode="json")
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=CREATED_STATUS, body=payload
    )
    return JSONResponse(status_code=CREATED_STATUS, content=payload)


@router.get(
    "/incidents/{incident_id}/links",
    summary="List an incident's links",
    description=(
        "Links in both directions, oldest first; `direction` says which way each one reads. "
        "Cursor-paginated; no total."
    ),
    response_model=ListEnvelope[IncidentLinkView],
)
async def list_incident_links(
    incident_id: uuid.UUID,
    workspace: WorkspaceSessionDependency,
    page_request: PageRequestDependency,
) -> ListEnvelope[IncidentLinkView]:
    page = await IncidentLinkService().list(
        workspace.session, workspace.access, incident_id, page_request
    )
    views = [IncidentLinkView.from_link(link, incident_id) for link in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))


@router.delete(
    "/incidents/{incident_id}/links/{link_id}",
    summary="Remove a link",
    description=(
        "Removes a link that this incident is either end of. Recorded on both incidents' "
        "timelines and in the audit chain. Requires an incident-writing role."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_incident_link(
    incident_id: uuid.UUID, link_id: uuid.UUID, workspace: IncidentWriteWorkspaceDependency
) -> Response:
    await IncidentLinkService().remove(workspace.session, workspace.access, incident_id, link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
