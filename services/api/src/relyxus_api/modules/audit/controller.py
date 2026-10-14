from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER, WorkspaceSessionDependency
from relyxus_api.modules.audit.model import ActorType
from relyxus_api.modules.audit.repository import AuditRepository
from relyxus_api.modules.audit.schema import (
    AuditEventSummary,
    ChainVerificationFailureView,
    ChainVerificationReport,
    RecordAuditEventRequest,
)
from relyxus_api.modules.audit.service import AuditService, NewAuditEvent
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.pagination import Page, PageRequestDependency
from relyxus_api.shared.observability.correlation import get_correlation_id

AUDIT_TAG = "audit"

router = APIRouter(prefix="/api/v1", tags=[AUDIT_TAG])


def _service() -> AuditService:
    return AuditService(AuditRepository())


@router.get(
    "/audit-events",
    summary="List audit events for the current workspace",
    description=(
        f"Cursor-paginated audit log for the workspace in `{WORKSPACE_HEADER}`. "
        "No total count is returned."
    ),
    response_model=ListEnvelope[AuditEventSummary],
)
async def list_audit_events(
    workspace: WorkspaceSessionDependency,
    page_request: PageRequestDependency,
) -> ListEnvelope[AuditEventSummary]:
    page = await _service().list_workspace_events(
        workspace.session, workspace.access.workspace_id, page_request
    )
    summaries = [AuditEventSummary.from_event(event) for event in page.items]
    return wrap_page(
        Page(items=summaries, next_cursor=page.next_cursor, limit=page.limit)
    )


@router.get(
    "/audit-events/chain-verification",
    summary="Verify the workspace audit hash chain",
    description="Recomputes every hash link for the current workspace chain offline.",
    response_model=SuccessEnvelope[ChainVerificationReport],
)
async def verify_audit_chain(
    workspace: WorkspaceSessionDependency,
) -> SuccessEnvelope[ChainVerificationReport]:
    failures = await _service().verify_chain(
        workspace.session, workspace.access.workspace_id
    )
    report = ChainVerificationReport(
        chain_id=workspace.access.workspace_id,
        is_valid=not failures,
        failures=[
            ChainVerificationFailureView(sequence=item.sequence, reason=item.reason)
            for item in failures
        ],
    )
    return wrap_success(report)


@router.post(
    "/audit-events",
    summary="Record an audit event in the current workspace",
    description=(
        f"Appends one hash-chained audit row for `{WORKSPACE_HEADER}`. "
        "Requires `Idempotency-Key` so retries replay the same response."
    ),
    response_model=SuccessEnvelope[AuditEventSummary],
    status_code=201,
)
async def record_audit_event(
    request: Request,
    workspace: WorkspaceSessionDependency,
    body: RecordAuditEventRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
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

    event = await _service().append(
        workspace.session,
        NewAuditEvent(
            organization_id=workspace.access.organization_id,
            workspace_id=workspace.access.workspace_id,
            actor_type=ActorType.USER,
            actor_user_id=workspace.access.user_id,
            effective_user_id=None,
            action=body.action,
            target_type=body.target_type,
            target_id=body.target_id,
            outcome=body.outcome,
            before_state=body.before_state,
            after_state=body.after_state,
            correlation_id=get_correlation_id(),
        ),
    )
    summary = AuditEventSummary.from_event(event)
    envelope = wrap_success(summary)
    payload = envelope.model_dump(mode="json")
    await idempotency.complete(
        workspace.session,
        reservation.record_id,
        status_code=201,
        body=payload,
    )
    return JSONResponse(status_code=201, content=payload)
