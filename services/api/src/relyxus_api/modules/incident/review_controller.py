import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WorkspaceSession, WorkspaceSessionDependency
from relyxus_api.modules.access.role_requirements import IncidentWriteWorkspaceDependency
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.incident.review_model import IncidentReview
from relyxus_api.modules.incident.review_schema import (
    ReviewView,
    TransitionReviewRequest,
    UpdateReviewRequest,
)
from relyxus_api.modules.incident.review_service import IncidentReviewService, ReviewChanges
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import SuccessEnvelope, wrap_success
from relyxus_api.shared.http.etag import format_weak_etag

REVIEWS_TAG = "incident-reviews"
CREATED_STATUS = 201
OK_STATUS = 200
REVIEW_PATH = "/incidents/{incident_id}/review"

router = APIRouter(prefix="/api/v1", tags=[REVIEWS_TAG])
IdempotencyKey = Annotated[str, Header(alias=IDEMPOTENCY_HEADER)]
IfMatch = Annotated[str | None, Header(alias="If-Match")]


def _body(review: IncidentReview) -> dict[str, object]:
    body: dict[str, object] = wrap_success(ReviewView.from_review(review)).model_dump(mode="json")
    return body


def _response(review: IncidentReview, status_code: int = OK_STATUS) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=_body(review),
        headers={"ETag": format_weak_etag(review.id, review.updated_at)},
    )


async def _idempotent(
    request: Request,
    workspace: WorkspaceSession,
    idempotency_key: str,
    payload: dict[str, object],
    status_code: int,
    act: Callable[[], Awaitable[IncidentReview]],
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
    review = await act()
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=status_code, body=_body(review)
    )
    return _response(review, status_code)


@router.get(
    REVIEW_PATH,
    summary="Get an incident's post-incident review",
    description=(
        "The review created when the incident was resolved (MPS-8A.11). 404 "
        "`INCIDENT_REVIEW_NOT_FOUND` before then. The `ETag` can be sent as `If-Match`."
    ),
    response_model=SuccessEnvelope[ReviewView],
)
async def get_review(incident_id: uuid.UUID, workspace: WorkspaceSessionDependency) -> Response:
    return _response(
        await IncidentReviewService().get(workspace.session, workspace.access, incident_id)
    )


@router.post(
    REVIEW_PATH,
    summary="Start a review for an incident resolved earlier",
    description=(
        "Reviews are created automatically on resolution. This creates one for a resolved or "
        "closed incident that has none (resolved before reviews existed). 409 if one exists. "
        f"Requires `{IDEMPOTENCY_HEADER}` and an incident-writing role."
    ),
    response_model=SuccessEnvelope[ReviewView],
    status_code=CREATED_STATUS,
)
async def start_review(
    request: Request,
    incident_id: uuid.UUID,
    workspace: IncidentWriteWorkspaceDependency,
    idempotency_key: IdempotencyKey,
) -> Response:
    return await _idempotent(
        request,
        workspace,
        idempotency_key,
        {},
        CREATED_STATUS,
        lambda: IncidentReviewService().start(workspace.session, workspace.access, incident_id),
    )


@router.patch(
    REVIEW_PATH,
    summary="Edit a review",
    description=(
        "Edit the summary and lessons learned while the review is a draft or in review, or "
        "reassign its owner (review owner, incident commander or owner). Optional `If-Match` "
        "returns 412 when the review changed since it was read."
    ),
    response_model=SuccessEnvelope[ReviewView],
)
async def update_review(
    incident_id: uuid.UUID,
    workspace: IncidentWriteWorkspaceDependency,
    body: UpdateReviewRequest,
    if_match: IfMatch = None,
) -> Response:
    review = await IncidentReviewService().update(
        workspace.session,
        workspace.access,
        incident_id,
        ReviewChanges(
            summary=body.summary,
            lessons_learned=body.lessons_learned,
            owner_user_id=body.owner_user_id,
            if_match=if_match,
        ),
    )
    return _response(review)


@router.post(
    f"{REVIEW_PATH}/transitions",
    summary="Move a review through its states",
    description=(
        "Draft → In review (needs a summary, and lessons learned for SEV1/SEV2), In review → "
        "Draft (send back), In review → Approved, Approved → Published (MPS-13.12). By the "
        f"review owner or a workspace owner. Requires `{IDEMPOTENCY_HEADER}`."
    ),
    response_model=SuccessEnvelope[ReviewView],
)
async def transition_review(
    request: Request,
    incident_id: uuid.UUID,
    workspace: WorkspaceSessionDependency,
    body: TransitionReviewRequest,
    idempotency_key: IdempotencyKey,
    if_match: IfMatch = None,
) -> Response:
    return await _idempotent(
        request,
        workspace,
        idempotency_key,
        body.model_dump(mode="json"),
        OK_STATUS,
        lambda: IncidentReviewService().transition(
            workspace.session, workspace.access, incident_id, body.target_state, if_match
        ),
    )
