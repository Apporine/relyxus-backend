from fastapi import APIRouter

from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER, WorkspaceSessionDependency
from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.schema import WorkspaceSummary
from relyxus_api.modules.access.service import WorkspaceAccessService
from relyxus_api.shared.auth.dependencies import AuthenticatedPrincipalDependency
from relyxus_api.shared.db.engine import DatabaseSessionDependency
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

WORKSPACES_TAG = "workspaces"

router = APIRouter(prefix="/api/v1", tags=[WORKSPACES_TAG])


def _build_service() -> WorkspaceAccessService:
    return WorkspaceAccessService(AccessRepository())


@router.get(
    "/me/workspaces",
    summary="Workspaces I can open",
    description=(
        "Every workspace the caller holds a role in, across organisations, with those roles. "
        "Backs the workspace picker. Cursor-paginated; no total is returned."
    ),
    response_model=ListEnvelope[WorkspaceSummary],
)
async def list_my_workspaces(
    principal: AuthenticatedPrincipalDependency,
    session: DatabaseSessionDependency,
    page_request: PageRequestDependency,
) -> ListEnvelope[WorkspaceSummary]:
    page = await _build_service().list_my_workspaces(session, principal, page_request)
    summaries = [WorkspaceSummary.from_listing(listing) for listing in page.items]
    return wrap_page(Page(items=summaries, next_cursor=page.next_cursor, limit=page.limit))


@router.get(
    "/workspaces/current",
    summary="Current workspace",
    description=(
        f"The workspace named in the `{WORKSPACE_HEADER}` header, verified against the caller's "
        "role grants, with those roles. Unknown and forbidden workspaces both return 403."
    ),
    response_model=SuccessEnvelope[WorkspaceSummary],
)
async def get_current_workspace(
    workspace: WorkspaceSessionDependency,
) -> SuccessEnvelope[WorkspaceSummary]:
    listing = await _build_service().describe_workspace(workspace.session, workspace.access)
    return wrap_success(WorkspaceSummary.from_listing(listing))
