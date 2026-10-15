import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER, WorkspaceSessionDependency
from relyxus_api.modules.access.role_requirements import WorkspaceStructureDependency
from relyxus_api.modules.catalog.model import CatalogService, ServiceTier
from relyxus_api.modules.catalog.schema import (
    CreateServiceRequest,
    ServiceView,
    UpdateServiceRequest,
)
from relyxus_api.modules.catalog.service import (
    CatalogFilters,
    CatalogServiceChanges,
    NewCatalogService,
    ServiceCatalog,
)
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

SERVICES_TAG = "services"
CREATED_STATUS = 201

router = APIRouter(prefix="/api/v1", tags=[SERVICES_TAG])


def _body(service: CatalogService) -> dict[str, object]:
    body: dict[str, object] = wrap_success(ServiceView.from_service(service)).model_dump(
        mode="json"
    )
    return body


def _headers(service: CatalogService) -> dict[str, str]:
    return {"ETag": format_weak_etag(service.id, service.updated_at)}


@router.post(
    "/services",
    summary="Add a service to the catalogue",
    description=(
        f"Creates a service in the workspace named in `{WORKSPACE_HEADER}` (MPS-20.08). The "
        "`key` never changes. The owner team must belong to the workspace. Owners and admins "
        f"only. Requires `{IDEMPOTENCY_HEADER}`."
    ),
    response_model=SuccessEnvelope[ServiceView],
    status_code=CREATED_STATUS,
)
async def create_service(
    request: Request,
    workspace: WorkspaceStructureDependency,
    body: CreateServiceRequest,
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

    service = await ServiceCatalog().create(
        workspace.session,
        workspace.access,
        NewCatalogService(
            key=body.key,
            name=body.name,
            description=body.description,
            tier=body.tier,
            environment=body.environment,
            owner_team_id=body.owner_team_id,
            labels=body.labels,
        ),
    )
    payload = _body(service)
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=CREATED_STATUS, body=payload
    )
    return JSONResponse(
        status_code=CREATED_STATUS,
        content=payload,
        headers={"Location": f"{request.url.path}/{service.id}", **_headers(service)},
    )


@router.get(
    "/services",
    summary="List the service catalogue",
    description=(
        "Services of the open workspace, oldest first; cursor-paginated, no total. Filter by "
        "`owner_team_id` and one or more `tier`. Archived services are left out unless "
        "`include_archived=true`."
    ),
    response_model=ListEnvelope[ServiceView],
)
async def list_services(
    workspace: WorkspaceSessionDependency,
    page_request: PageRequestDependency,
    owner_team_id: uuid.UUID | None = None,
    tier: Annotated[list[ServiceTier] | None, Query()] = None,
    include_archived: bool = False,
) -> ListEnvelope[ServiceView]:
    filters = CatalogFilters(
        owner_team_id=owner_team_id,
        tiers=frozenset(tier or ()),
        include_archived=include_archived,
    )
    page = await ServiceCatalog().list(workspace.session, workspace.access, filters, page_request)
    views = [ServiceView.from_service(service) for service in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))


@router.get(
    "/services/{service_id}",
    summary="Get a service",
    description="Services of other workspaces return 404, like unknown IDs.",
    response_model=SuccessEnvelope[ServiceView],
)
async def get_service(service_id: uuid.UUID, workspace: WorkspaceSessionDependency) -> Response:
    service = await ServiceCatalog().get(workspace.session, workspace.access, service_id)
    return JSONResponse(content=_body(service), headers=_headers(service))


@router.patch(
    "/services/{service_id}",
    summary="Change or archive a service",
    description=(
        "Partial update; the key never changes and `labels` replaces the whole set. "
        "`is_archived` archives or restores the service, keeping its values. Owners and "
        "admins only. Optional `If-Match` returns 412 when the service changed."
    ),
    response_model=SuccessEnvelope[ServiceView],
)
async def update_service(
    service_id: uuid.UUID,
    workspace: WorkspaceStructureDependency,
    body: UpdateServiceRequest,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    service = await ServiceCatalog().update(
        workspace.session,
        workspace.access,
        service_id,
        CatalogServiceChanges(
            changed_fields=frozenset(body.model_fields_set),
            name=body.name,
            description=body.description,
            tier=body.tier,
            environment=body.environment,
            owner_team_id=body.owner_team_id,
            labels=body.labels,
            is_archived=body.is_archived,
            if_match=if_match,
        ),
    )
    return JSONResponse(content=_body(service), headers=_headers(service))
