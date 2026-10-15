import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WorkspaceSession, WorkspaceSessionDependency
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.incident.handoff_model import IncidentRoleHandoff
from relyxus_api.modules.incident.handoff_schema import HandoffView, RequestHandoffRequest
from relyxus_api.modules.incident.handoff_service import IncidentHandoffService
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

HANDOFFS_TAG = "incident-handoffs"
CREATED_STATUS = 201
OK_STATUS = 200

router = APIRouter(prefix="/api/v1", tags=[HANDOFFS_TAG])
IdempotencyKey = Annotated[str, Header(alias=IDEMPOTENCY_HEADER)]


async def _idempotent(
    request: Request,
    workspace: WorkspaceSession,
    idempotency_key: str,
    payload: dict[str, object],
    status_code: int,
    act: Callable[[], Awaitable[IncidentRoleHandoff]],
) -> Response:
    idempotency = IdempotencyService()
    reservation = await idempotency.begin(
        workspace.session,
        organization_id=workspace.access.organization_id,
        idempotency_key=idempotency_key,
        method=request.method,
        path=request.url.path,
        payload=payload,
    )
    if isinstance(reservation, IdempotencyReplay):
        return JSONResponse(status_code=reservation.status_code, content=reservation.body)
    handoff = await act()
    body = wrap_success(HandoffView.from_handoff(handoff)).model_dump(mode="json")
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=status_code, body=body
    )
    return JSONResponse(status_code=status_code, content=body)


@router.post(
    "/incidents/{incident_id}/handoffs",
    summary="Request a role handoff",
    description=(
        "Proposes handing one incident role from its current holder to another workspace "
        "member (MPS-11.23). The handoff package is captured now. The role does not move "
        "until the incoming person accepts. One pending handoff per role. Allowed for the "
        f"current holder, an incident commander or an owner. Requires `{IDEMPOTENCY_HEADER}`."
    ),
    response_model=SuccessEnvelope[HandoffView],
    status_code=CREATED_STATUS,
)
async def request_handoff(
    request: Request,
    incident_id: uuid.UUID,
    workspace: WorkspaceSessionDependency,
    body: RequestHandoffRequest,
    idempotency_key: IdempotencyKey,
) -> Response:
    return await _idempotent(
        request,
        workspace,
        idempotency_key,
        body.model_dump(mode="json"),
        CREATED_STATUS,
        lambda: IncidentHandoffService().request(
            workspace.session, workspace.access, incident_id, body.role, body.to_user_id
        ),
    )


@router.get(
    "/incidents/{incident_id}/handoffs",
    summary="List an incident's role handoffs",
    description="Pending, accepted and cancelled handoffs, oldest first; cursor-paginated.",
    response_model=ListEnvelope[HandoffView],
)
async def list_handoffs(
    incident_id: uuid.UUID,
    workspace: WorkspaceSessionDependency,
    page_request: PageRequestDependency,
) -> ListEnvelope[HandoffView]:
    page = await IncidentHandoffService().list(
        workspace.session, workspace.access, incident_id, page_request
    )
    views = [HandoffView.from_handoff(handoff) for handoff in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))


@router.post(
    "/incidents/{incident_id}/handoffs/{handoff_id}/accept",
    summary="Accept a role handoff",
    description=(
        "The incoming person acknowledges the handoff (MPS-11.24); the role moves to them and "
        "the timeline records outgoing, incoming and time. Refused if the outgoing person no "
        f"longer holds the role. Requires `{IDEMPOTENCY_HEADER}`."
    ),
    response_model=SuccessEnvelope[HandoffView],
)
async def accept_handoff(
    request: Request,
    incident_id: uuid.UUID,
    handoff_id: uuid.UUID,
    workspace: WorkspaceSessionDependency,
    idempotency_key: IdempotencyKey,
) -> Response:
    return await _idempotent(
        request,
        workspace,
        idempotency_key,
        {},
        OK_STATUS,
        lambda: IncidentHandoffService().accept(
            workspace.session, workspace.access, incident_id, handoff_id
        ),
    )


@router.post(
    "/incidents/{incident_id}/handoffs/{handoff_id}/cancel",
    summary="Cancel or decline a role handoff",
    description=(
        "Cancels a pending handoff; the incoming person cancelling it declines it. Allowed for "
        "the requester, either person, an incident commander or an owner. Requires "
        f"`{IDEMPOTENCY_HEADER}`."
    ),
    response_model=SuccessEnvelope[HandoffView],
)
async def cancel_handoff(
    request: Request,
    incident_id: uuid.UUID,
    handoff_id: uuid.UUID,
    workspace: WorkspaceSessionDependency,
    idempotency_key: IdempotencyKey,
) -> Response:
    return await _idempotent(
        request,
        workspace,
        idempotency_key,
        {},
        OK_STATUS,
        lambda: IncidentHandoffService().cancel(
            workspace.session, workspace.access, incident_id, handoff_id
        ),
    )
