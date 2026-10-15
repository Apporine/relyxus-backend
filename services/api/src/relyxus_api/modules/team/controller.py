import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response, status
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER, WorkspaceSessionDependency
from relyxus_api.modules.access.role_requirements import WorkspaceStructureDependency
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.team.model import Team
from relyxus_api.modules.team.schema import (
    CreateTeamRequest,
    TeamMemberView,
    TeamView,
    UpdateTeamRequest,
)
from relyxus_api.modules.team.service import NewTeam, TeamChanges, TeamService
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

TEAMS_TAG = "teams"
CREATED_STATUS = 201

router = APIRouter(prefix="/api/v1", tags=[TEAMS_TAG])


def _body(team: Team) -> dict[str, object]:
    body: dict[str, object] = wrap_success(TeamView.from_team(team)).model_dump(mode="json")
    return body


def _headers(team: Team) -> dict[str, str]:
    return {"ETag": format_weak_etag(team.id, team.updated_at)}


@router.post(
    "/teams",
    summary="Create a team",
    description=(
        f"Creates a team in the workspace named in `{WORKSPACE_HEADER}` (MPS-14.01). The "
        "`key` is the team's stable identifier and never changes. Owners and admins only. "
        f"Requires `{IDEMPOTENCY_HEADER}`."
    ),
    response_model=SuccessEnvelope[TeamView],
    status_code=CREATED_STATUS,
)
async def create_team(
    request: Request,
    workspace: WorkspaceStructureDependency,
    body: CreateTeamRequest,
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

    team = await TeamService().create(
        workspace.session,
        workspace.access,
        NewTeam(key=body.key, name=body.name, description=body.description),
    )
    payload = _body(team)
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=CREATED_STATUS, body=payload
    )
    return JSONResponse(
        status_code=CREATED_STATUS,
        content=payload,
        headers={"Location": f"{request.url.path}/{team.id}", **_headers(team)},
    )


@router.get(
    "/teams",
    summary="List teams",
    description="Teams of the open workspace, oldest first; cursor-paginated, no total.",
    response_model=ListEnvelope[TeamView],
)
async def list_teams(
    workspace: WorkspaceSessionDependency, page_request: PageRequestDependency
) -> ListEnvelope[TeamView]:
    page = await TeamService().list(workspace.session, workspace.access, page_request)
    views = [TeamView.from_team(team) for team in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))


@router.get(
    "/teams/{team_id}",
    summary="Get a team",
    description="Teams of other workspaces return 404, like unknown IDs.",
    response_model=SuccessEnvelope[TeamView],
)
async def get_team(team_id: uuid.UUID, workspace: WorkspaceSessionDependency) -> Response:
    team = await TeamService().get(workspace.session, workspace.access, team_id)
    return JSONResponse(content=_body(team), headers=_headers(team))


@router.patch(
    "/teams/{team_id}",
    summary="Rename a team or change its description",
    description=(
        "The key never changes. Owners and admins only. Optional `If-Match` returns 412 when "
        "the team changed since it was read."
    ),
    response_model=SuccessEnvelope[TeamView],
)
async def update_team(
    team_id: uuid.UUID,
    workspace: WorkspaceStructureDependency,
    body: UpdateTeamRequest,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    team = await TeamService().update(
        workspace.session,
        workspace.access,
        team_id,
        TeamChanges(
            changed_fields=frozenset(body.model_fields_set),
            name=body.name,
            description=body.description,
            if_match=if_match,
        ),
    )
    return JSONResponse(content=_body(team), headers=_headers(team))


@router.get(
    "/teams/{team_id}/members",
    summary="List a team's members",
    description="Oldest first; cursor-paginated, no total.",
    response_model=ListEnvelope[TeamMemberView],
)
async def list_team_members(
    team_id: uuid.UUID, workspace: WorkspaceSessionDependency, page_request: PageRequestDependency
) -> ListEnvelope[TeamMemberView]:
    page = await TeamService().list_members(
        workspace.session, workspace.access, team_id, page_request
    )
    views = [TeamMemberView.from_member(member) for member in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))


@router.put(
    "/teams/{team_id}/members/{user_id}",
    summary="Add a team member",
    description=(
        "Adds a workspace member to the team. Idempotent. Owners and admins only. Recorded in "
        "the workspace audit chain."
    ),
    response_model=SuccessEnvelope[TeamMemberView],
)
async def add_team_member(
    team_id: uuid.UUID, user_id: uuid.UUID, workspace: WorkspaceStructureDependency
) -> SuccessEnvelope[TeamMemberView]:
    member = await TeamService().add_member(workspace.session, workspace.access, team_id, user_id)
    return wrap_success(TeamMemberView.from_member(member))


@router.delete(
    "/teams/{team_id}/members/{user_id}",
    summary="Remove a team member",
    description="Owners and admins only. 404 if the person is not a member.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_team_member(
    team_id: uuid.UUID, user_id: uuid.UUID, workspace: WorkspaceStructureDependency
) -> Response:
    await TeamService().remove_member(workspace.session, workspace.access, team_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
