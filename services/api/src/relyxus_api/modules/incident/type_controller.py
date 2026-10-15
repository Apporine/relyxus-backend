import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER, WorkspaceSessionDependency
from relyxus_api.modules.access.role_requirements import WorkspaceStructureDependency
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.incident.type_model import IncidentType
from relyxus_api.modules.incident.type_schema import (
    CreateIncidentTypeRequest,
    IncidentTypeView,
    UpdateIncidentTypeRequest,
)
from relyxus_api.modules.incident.type_service import (
    IncidentTypeChanges,
    IncidentTypeService,
    NewIncidentType,
)
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

TYPES_TAG = "incident-types"
CREATED_STATUS = 201
OK_STATUS = 200

router = APIRouter(prefix="/api/v1", tags=[TYPES_TAG])


def _body(incident_type: IncidentType) -> dict[str, object]:
    body: dict[str, object] = wrap_success(IncidentTypeView.from_type(incident_type)).model_dump(
        mode="json"
    )
    return body


def _headers(incident_type: IncidentType) -> dict[str, str]:
    return {"ETag": format_weak_etag(incident_type.id, incident_type.updated_at)}


@router.post(
    "/incident-types",
    summary="Create an incident type",
    description=(
        f"Creates an incident type in the workspace named in `{WORKSPACE_HEADER}` (MPS-8A.01) "
        "with its allowed severities, default severity and default visibility. Version 1 is "
        f"recorded. Owners and admins. Requires `{IDEMPOTENCY_HEADER}`."
    ),
    response_model=SuccessEnvelope[IncidentTypeView],
    status_code=CREATED_STATUS,
)
async def create_incident_type(
    request: Request,
    workspace: WorkspaceStructureDependency,
    body: CreateIncidentTypeRequest,
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
    incident_type = await IncidentTypeService().create(
        workspace.session,
        workspace.access,
        NewIncidentType(
            key=body.key,
            name=body.name,
            description=body.description,
            allowed_severities=tuple(body.allowed_severities),
            default_severity=body.default_severity,
            default_visibility=body.default_visibility,
        ),
    )
    payload = _body(incident_type)
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=CREATED_STATUS, body=payload
    )
    return JSONResponse(
        status_code=CREATED_STATUS, content=payload, headers=_headers(incident_type)
    )


@router.post(
    "/incident-types/defaults",
    summary="Install the default incident types",
    description=(
        "Adds the nine default types of MPS-8A.02 (Production outage, …, Internal operational "
        "event) that the workspace does not have yet, matched by key; existing types are "
        "untouched. Security event is invite-only and Data incident restricted by default. "
        "Returns the types created (empty when all exist). Owners and admins."
    ),
    response_model=SuccessEnvelope[list[IncidentTypeView]],
)
async def install_default_incident_types(
    workspace: WorkspaceStructureDependency,
) -> SuccessEnvelope[list[IncidentTypeView]]:
    created = await IncidentTypeService().install_defaults(workspace.session, workspace.access)
    return wrap_success([IncidentTypeView.from_type(incident_type) for incident_type in created])


@router.get(
    "/incident-types",
    summary="List incident types",
    description="Oldest first; archived types only with `include_archived=true`.",
    response_model=ListEnvelope[IncidentTypeView],
)
async def list_incident_types(
    workspace: WorkspaceSessionDependency,
    page_request: PageRequestDependency,
    include_archived: bool = False,
) -> ListEnvelope[IncidentTypeView]:
    page = await IncidentTypeService().list(
        workspace.session, workspace.access, include_archived, page_request
    )
    views = [IncidentTypeView.from_type(incident_type) for incident_type in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))


@router.get(
    "/incident-types/{type_id}",
    summary="Get an incident type",
    description="Earlier versions are under `/configuration/incident_type/{id}/versions`.",
    response_model=SuccessEnvelope[IncidentTypeView],
)
async def get_incident_type(type_id: uuid.UUID, workspace: WorkspaceSessionDependency) -> Response:
    incident_type = await IncidentTypeService().get(workspace.session, workspace.access, type_id)
    return JSONResponse(content=_body(incident_type), headers=_headers(incident_type))


@router.patch(
    "/incident-types/{type_id}",
    summary="Change or archive an incident type",
    description=(
        "Each change creates a new type version (MPS-8A.06); incidents keep the version they "
        "were declared under. The default severity must stay among the allowed severities. "
        "Owners and admins. Optional `If-Match`."
    ),
    response_model=SuccessEnvelope[IncidentTypeView],
)
async def update_incident_type(
    type_id: uuid.UUID,
    workspace: WorkspaceStructureDependency,
    body: UpdateIncidentTypeRequest,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    incident_type = await IncidentTypeService().update(
        workspace.session,
        workspace.access,
        type_id,
        IncidentTypeChanges(
            changed_fields=frozenset(body.model_fields_set),
            name=body.name,
            description=body.description,
            allowed_severities=(
                None if body.allowed_severities is None else tuple(body.allowed_severities)
            ),
            default_severity=body.default_severity,
            default_visibility=body.default_visibility,
            is_archived=body.is_archived,
            if_match=if_match,
        ),
    )
    return JSONResponse(content=_body(incident_type), headers=_headers(incident_type))
