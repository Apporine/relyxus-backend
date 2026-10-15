import uuid

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WorkspaceSessionDependency
from relyxus_api.modules.incident.schema import IncidentView
from relyxus_api.modules.incident.visibility_schema import (
    AccessGrantView,
    ChangeVisibilityRequest,
    CreateAccessGrantRequest,
)
from relyxus_api.modules.incident.visibility_service import (
    IncidentVisibilityService,
    NewAccessGrant,
)
from relyxus_api.shared.http.envelope import SuccessEnvelope, wrap_success
from relyxus_api.shared.http.etag import format_weak_etag

VISIBILITY_TAG = "incident-visibility"
CREATED_STATUS = 201

router = APIRouter(prefix="/api/v1", tags=[VISIBILITY_TAG])


@router.put(
    "/incidents/{incident_id}/visibility",
    summary="Change who can see an incident",
    description=(
        "Sets the visibility mode (MPS-8A.23): `workspace`, `restricted` (named people, teams "
        "or roles), `invite_only` or `confidential` (named people only). People without "
        "access get 404 for the incident and everything under it. The caller keeps access "
        "through a person grant. Owners and incident commanders; needs a `reason`."
    ),
    response_model=SuccessEnvelope[IncidentView],
)
async def change_visibility(
    incident_id: uuid.UUID, workspace: WorkspaceSessionDependency, body: ChangeVisibilityRequest
) -> Response:
    incident = await IncidentVisibilityService().change_visibility(
        workspace.session, workspace.access, incident_id, body.visibility, body.reason
    )
    return JSONResponse(
        content=wrap_success(IncidentView.from_incident(incident)).model_dump(mode="json"),
        headers={"ETag": format_weak_etag(incident.id, incident.updated_at)},
    )


@router.get(
    "/incidents/{incident_id}/access-grants",
    summary="List who has been granted access",
    description="Grants of the incident, oldest first (at most 200), expired ones included.",
    response_model=SuccessEnvelope[list[AccessGrantView]],
)
async def list_access_grants(
    incident_id: uuid.UUID, workspace: WorkspaceSessionDependency
) -> SuccessEnvelope[list[AccessGrantView]]:
    grants = await IncidentVisibilityService().list_grants(
        workspace.session, workspace.access, incident_id
    )
    return wrap_success([AccessGrantView.from_grant(grant) for grant in grants])


@router.post(
    "/incidents/{incident_id}/access-grants",
    summary="Grant access to an incident",
    description=(
        "Grants one workspace member, team or workspace role access, with a reason and an "
        "optional expiry (MPS-20.30). Team and role grants count only for `restricted` "
        "incidents. Owners and incident commanders."
    ),
    response_model=SuccessEnvelope[AccessGrantView],
    status_code=CREATED_STATUS,
)
async def create_access_grant(
    incident_id: uuid.UUID, workspace: WorkspaceSessionDependency, body: CreateAccessGrantRequest
) -> Response:
    grant = await IncidentVisibilityService().grant(
        workspace.session,
        workspace.access,
        incident_id,
        NewAccessGrant(
            user_id=body.user_id,
            team_id=body.team_id,
            role=body.role,
            reason=body.reason,
            expires_at=body.expires_at,
        ),
    )
    return JSONResponse(
        status_code=CREATED_STATUS,
        content=wrap_success(AccessGrantView.from_grant(grant)).model_dump(mode="json"),
    )


@router.delete(
    "/incidents/{incident_id}/access-grants/{grant_id}",
    summary="Revoke an access grant",
    description="Owners and incident commanders. Takes effect on the next request.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_access_grant(
    incident_id: uuid.UUID, grant_id: uuid.UUID, workspace: WorkspaceSessionDependency
) -> Response:
    await IncidentVisibilityService().revoke(
        workspace.session, workspace.access, incident_id, grant_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
