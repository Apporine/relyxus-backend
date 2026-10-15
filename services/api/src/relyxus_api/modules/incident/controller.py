import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER, WorkspaceSessionDependency
from relyxus_api.modules.access.role_requirements import IncidentWriteWorkspaceDependency
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.model import Incident, IncidentSeverity
from relyxus_api.modules.incident.schema import (
    DeclareIncidentRequest,
    IncidentView,
    TransitionIncidentRequest,
    UpdateIncidentRequest,
)
from relyxus_api.modules.incident.service import IncidentFilters, IncidentService, NewIncident
from relyxus_api.modules.incident.transition_service import (
    IncidentTransitionService,
    TransitionCommand,
)
from relyxus_api.modules.incident.update_service import IncidentChanges, IncidentUpdateService
from relyxus_api.shared.config.settings import Settings
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

INCIDENTS_TAG = "incidents"
CREATED_STATUS = 201
OK_STATUS = 200

router = APIRouter(prefix="/api/v1", tags=[INCIDENTS_TAG])


def _incident_body(incident: Incident) -> dict[str, object]:
    body: dict[str, object] = wrap_success(IncidentView.from_incident(incident)).model_dump(
        mode="json"
    )
    return body


def _etag_headers(incident: Incident) -> dict[str, str]:
    return {"ETag": format_weak_etag(incident.id, incident.updated_at)}


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
    payload = _incident_body(incident)
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=CREATED_STATUS, body=payload
    )
    return JSONResponse(
        status_code=CREATED_STATUS,
        content=payload,
        headers={"Location": f"{request.url.path}/{incident.id}", **_etag_headers(incident)},
    )


@router.get(
    "/incidents",
    summary="List incidents",
    description=(
        f"Incidents in the workspace named in `{WORKSPACE_HEADER}`, newest first. Filter by one "
        "or more `lifecycle_state` and `severity` values (repeat the parameter). "
        "Cursor-paginated; no total is returned."
    ),
    response_model=ListEnvelope[IncidentView],
)
async def list_incidents(
    workspace: WorkspaceSessionDependency,
    page_request: PageRequestDependency,
    lifecycle_state: Annotated[list[IncidentLifecycleState] | None, Query()] = None,
    severity: Annotated[list[IncidentSeverity] | None, Query()] = None,
) -> ListEnvelope[IncidentView]:
    filters = IncidentFilters(
        lifecycle_states=frozenset(lifecycle_state or ()), severities=frozenset(severity or ())
    )
    page = await IncidentService().list(workspace.session, workspace.access, filters, page_request)
    views = [IncidentView.from_incident(incident) for incident in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))


@router.get(
    "/incidents/{incident_id}",
    summary="Get an incident",
    description=(
        f"One incident in the workspace named in `{WORKSPACE_HEADER}`. Incidents in other "
        "workspaces return 404, the same as incidents that do not exist. The `ETag` can be "
        "sent as `If-Match` on transitions."
    ),
    response_model=SuccessEnvelope[IncidentView],
)
async def get_incident(incident_id: uuid.UUID, workspace: WorkspaceSessionDependency) -> Response:
    incident = await IncidentService().get(workspace.session, workspace.access, incident_id)
    return JSONResponse(content=_incident_body(incident), headers=_etag_headers(incident))


@router.post(
    "/incidents/{incident_id}/transitions",
    summary="Move an incident through its lifecycle",
    description=(
        "Applies one lifecycle transition (ADR-0004) and records it in the workspace audit "
        "chain in the same transaction. Each move is limited to the roles MPS-8A names; "
        "cancelling and reopening need a `reason`; merging needs `merged_into_incident_id`; "
        "reopening is allowed only within the configured window after resolution; closing "
        "returns 409 until post-incident review sign-off exists. Optional `If-Match` returns "
        f"412 if the incident changed since it was read. Requires `{IDEMPOTENCY_HEADER}`."
    ),
    response_model=SuccessEnvelope[IncidentView],
)
async def transition_incident(
    request: Request,
    incident_id: uuid.UUID,
    workspace: WorkspaceSessionDependency,
    body: TransitionIncidentRequest,
    idempotency_key: Annotated[str, Header(alias=IDEMPOTENCY_HEADER)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
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

    settings: Settings = request.app.state.settings
    service = IncidentTransitionService(
        reopen_window=timedelta(days=settings.incident_reopen_window_days)
    )
    incident = await service.transition(
        workspace.session,
        workspace.access,
        TransitionCommand(
            incident_id=incident_id,
            target_state=body.target_state,
            reason=body.reason,
            merged_into_incident_id=body.merged_into_incident_id,
            if_match=if_match,
        ),
    )
    payload = _incident_body(incident)
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=OK_STATUS, body=payload
    )
    return JSONResponse(content=payload, headers=_etag_headers(incident))


@router.patch(
    "/incidents/{incident_id}",
    summary="Change an incident's title or severity",
    description=(
        "Partial update of an open incident. Changing severity needs a `reason` (a human "
        "override, MPS-8.06). Optional `If-Match` returns 412 if the incident changed since "
        "it was read. Recorded in the workspace audit chain in the same transaction. "
        "Requires the owner, admin, incident commander or responder role."
    ),
    response_model=SuccessEnvelope[IncidentView],
)
async def update_incident(
    incident_id: uuid.UUID,
    workspace: IncidentWriteWorkspaceDependency,
    body: UpdateIncidentRequest,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    incident = await IncidentUpdateService().update(
        workspace.session,
        workspace.access,
        IncidentChanges(
            incident_id=incident_id,
            title=body.title,
            severity=body.severity,
            reason=body.reason,
            if_match=if_match,
        ),
    )
    return JSONResponse(content=_incident_body(incident), headers=_etag_headers(incident))
