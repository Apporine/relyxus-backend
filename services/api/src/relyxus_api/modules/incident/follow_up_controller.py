import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WorkspaceSessionDependency
from relyxus_api.modules.access.role_requirements import IncidentWriteWorkspaceDependency
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.incident.follow_up_model import IncidentFollowUp
from relyxus_api.modules.incident.follow_up_schema import (
    CreateFollowUpRequest,
    FollowUpView,
    UpdateFollowUpRequest,
)
from relyxus_api.modules.incident.follow_up_service import (
    FollowUpChanges,
    IncidentFollowUpService,
    NewFollowUp,
)
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

FOLLOW_UPS_TAG = "incident-follow-ups"
CREATED_STATUS = 201

router = APIRouter(prefix="/api/v1", tags=[FOLLOW_UPS_TAG])


def _body(follow_up: IncidentFollowUp) -> dict[str, object]:
    body: dict[str, object] = wrap_success(FollowUpView.from_follow_up(follow_up)).model_dump(
        mode="json"
    )
    return body


def _etag(follow_up: IncidentFollowUp) -> dict[str, str]:
    return {"ETag": format_weak_etag(follow_up.id, follow_up.updated_at)}


@router.post(
    "/incidents/{incident_id}/follow-ups",
    summary="Create a follow-up",
    description=(
        "Adds post-incident work to a resolved or closed incident (MPS-26.02). The owner, if "
        "given, must be a workspace member. `is_mandatory` defaults to true for SEV1/SEV2. "
        f"Requires `{IDEMPOTENCY_HEADER}` and an incident-writing role."
    ),
    response_model=SuccessEnvelope[FollowUpView],
    status_code=CREATED_STATUS,
)
async def create_follow_up(
    request: Request,
    incident_id: uuid.UUID,
    workspace: IncidentWriteWorkspaceDependency,
    body: CreateFollowUpRequest,
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

    follow_up = await IncidentFollowUpService().create(
        workspace.session,
        workspace.access,
        incident_id,
        NewFollowUp(
            title=body.title,
            owner_user_id=body.owner_user_id,
            due_at=body.due_at,
            is_mandatory=body.is_mandatory,
        ),
    )
    payload = _body(follow_up)
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=CREATED_STATUS, body=payload
    )
    return JSONResponse(status_code=CREATED_STATUS, content=payload, headers=_etag(follow_up))


@router.get(
    "/incidents/{incident_id}/follow-ups",
    summary="List an incident's follow-ups",
    description="Oldest first, cursor-paginated; no total. Visibility follows the incident.",
    response_model=ListEnvelope[FollowUpView],
)
async def list_follow_ups(
    incident_id: uuid.UUID,
    workspace: WorkspaceSessionDependency,
    page_request: PageRequestDependency,
) -> ListEnvelope[FollowUpView]:
    page = await IncidentFollowUpService().list(
        workspace.session, workspace.access, incident_id, page_request
    )
    views = [FollowUpView.from_follow_up(follow_up) for follow_up in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))


@router.patch(
    "/incidents/{incident_id}/follow-ups/{follow_up_id}",
    summary="Update a follow-up",
    description=(
        "Change title, owner, due time, mandatory flag or status. Cancelling needs a `reason`; "
        "done and cancelled are final. Send `owner_user_id` or `due_at` as null to clear them. "
        "Optional `If-Match` returns 412 when the follow-up changed since it was read."
    ),
    response_model=SuccessEnvelope[FollowUpView],
)
async def update_follow_up(
    incident_id: uuid.UUID,
    follow_up_id: uuid.UUID,
    workspace: IncidentWriteWorkspaceDependency,
    body: UpdateFollowUpRequest,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    follow_up = await IncidentFollowUpService().update(
        workspace.session,
        workspace.access,
        incident_id,
        follow_up_id,
        FollowUpChanges(
            changed_fields=frozenset(body.model_fields_set),
            title=body.title,
            owner_user_id=body.owner_user_id,
            due_at=body.due_at,
            is_mandatory=body.is_mandatory,
            status=body.status,
            reason=body.reason,
            if_match=if_match,
        ),
    )
    return JSONResponse(content=_body(follow_up), headers=_etag(follow_up))
