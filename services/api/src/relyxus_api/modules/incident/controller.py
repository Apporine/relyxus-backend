import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER, WorkspaceSessionDependency
from relyxus_api.modules.access.role_requirements import IncidentWriteWorkspaceDependency
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.incident.schema import DeclareIncidentRequest, IncidentView
from relyxus_api.modules.incident.service import IncidentService, NewIncident
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import SuccessEnvelope, wrap_success

INCIDENTS_TAG = "incidents"
CREATED_STATUS = 201

router = APIRouter(prefix="/api/v1", tags=[INCIDENTS_TAG])


@router.post(
    "/incidents",
    summary="Declare an incident or save a draft",
    description=(
        f"Creates an incident in the workspace named in `{WORKSPACE_HEADER}`. By default it is "
        "declared (triage → investigating); `is_declared: false` keeps it in triage as a draft. "
        "The change is written to the workspace audit chain in the same transaction. "
        f"Requires `{IDEMPOTENCY_HEADER}`; a retry with the same key replays the first "
        "response. Requires the owner, admin, incident commander or responder role."
    ),
    response_model=SuccessEnvelope[IncidentView],
    status_code=CREATED_STATUS,
)
async def declare_incident(
    request: Request,
    workspace: IncidentWriteWorkspaceDependency,
    body: DeclareIncidentRequest,
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

    incident = await IncidentService().create(
        workspace.session,
        workspace.access,
        NewIncident(title=body.title, severity=body.severity, is_declared=body.is_declared),
    )
    payload = wrap_success(IncidentView.from_incident(incident)).model_dump(mode="json")
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=CREATED_STATUS, body=payload
    )
    return JSONResponse(
        status_code=CREATED_STATUS,
        content=payload,
        headers={"Location": f"{request.url.path}/{incident.id}"},
    )


@router.get(
    "/incidents/{incident_id}",
    summary="Get an incident",
    description=(
        f"One incident in the workspace named in `{WORKSPACE_HEADER}`. Incidents in other "
        "workspaces return 404, the same as incidents that do not exist."
    ),
    response_model=SuccessEnvelope[IncidentView],
)
async def get_incident(
    incident_id: uuid.UUID, workspace: WorkspaceSessionDependency
) -> SuccessEnvelope[IncidentView]:
    incident = await IncidentService().get(workspace.session, workspace.access, incident_id)
    return wrap_success(IncidentView.from_incident(incident))
