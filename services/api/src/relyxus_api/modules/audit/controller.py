from fastapi import APIRouter

from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER, WorkspaceSessionDependency
from relyxus_api.modules.audit.repository import AuditRepository
from relyxus_api.modules.audit.schema import (
    AuditEventSummary,
    ChainVerificationFailureView,
    ChainVerificationReport,
)
from relyxus_api.modules.audit.service import AuditService
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

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
