import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WorkspaceSessionDependency
from relyxus_api.modules.access.role_requirements import WorkspaceStructureDependency
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.incident.field_model import CustomFieldDefinition
from relyxus_api.modules.incident.field_schema import (
    CreateCustomFieldRequest,
    CustomFieldView,
    UpdateCustomFieldRequest,
)
from relyxus_api.modules.incident.field_service import (
    CustomFieldChanges,
    CustomFieldService,
    NewCustomField,
)
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

FIELDS_TAG = "custom-fields"
CREATED_STATUS = 201

router = APIRouter(prefix="/api/v1", tags=[FIELDS_TAG])


def _body(found: CustomFieldDefinition) -> dict[str, object]:
    body: dict[str, object] = wrap_success(CustomFieldView.from_field(found)).model_dump(
        mode="json"
    )
    return body


def _headers(found: CustomFieldDefinition) -> dict[str, str]:
    return {"ETag": format_weak_etag(found.id, found.updated_at)}


@router.post(
    "/custom-fields",
    summary="Define a custom incident field",
    description=(
        "Adds a field to the workspace's library (MPS-8A.03): text, number, currency, "
        "date-time, yes/no, single or multiple choice, user, team, service or URL. Optional "
        "display condition by incident type and severity, and a stage it is required at "
        f"(MPS-8A.04). Version 1 is recorded. Owners and admins. Requires `{IDEMPOTENCY_HEADER}`."
    ),
    response_model=SuccessEnvelope[CustomFieldView],
    status_code=CREATED_STATUS,
)
async def create_custom_field(
    request: Request,
    workspace: WorkspaceStructureDependency,
    body: CreateCustomFieldRequest,
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
    created = await CustomFieldService().create(
        workspace.session,
        workspace.access,
        NewCustomField(
            key=body.key,
            label=body.label,
            description=body.description,
            data_type=body.data_type,
            options=tuple(option.to_option() for option in body.options),
            display_condition=body.display_condition.to_condition(),
            required_at_stage=body.required_at_stage,
        ),
    )
    payload = _body(created)
    await idempotency.complete(
        workspace.session, reservation.record_id, status_code=CREATED_STATUS, body=payload
    )
    return JSONResponse(status_code=CREATED_STATUS, content=payload, headers=_headers(created))


@router.get(
    "/custom-fields",
    summary="List custom fields",
    description="Oldest first; archived fields only with `include_archived=true`.",
    response_model=ListEnvelope[CustomFieldView],
)
async def list_custom_fields(
    workspace: WorkspaceSessionDependency,
    page_request: PageRequestDependency,
    include_archived: bool = False,
) -> ListEnvelope[CustomFieldView]:
    page = await CustomFieldService().list(
        workspace.session, workspace.access, include_archived, page_request
    )
    views = [CustomFieldView.from_field(found) for found in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))


@router.get(
    "/custom-fields/{field_id}",
    summary="Get a custom field",
    description="Earlier versions are under `/configuration/custom_field/{id}/versions`.",
    response_model=SuccessEnvelope[CustomFieldView],
)
async def get_custom_field(field_id: uuid.UUID, workspace: WorkspaceSessionDependency) -> Response:
    found = await CustomFieldService().get(workspace.session, workspace.access, field_id)
    return JSONResponse(content=_body(found), headers=_headers(found))


@router.patch(
    "/custom-fields/{field_id}",
    summary="Change or archive a custom field",
    description=(
        "Each change creates a new field version (MPS-8A.06). Key and data type never change. "
        "Archiving deletes the field from forms; existing values stay (MPS-8A.05). Owners and "
        "admins. Optional `If-Match`."
    ),
    response_model=SuccessEnvelope[CustomFieldView],
)
async def update_custom_field(
    field_id: uuid.UUID,
    workspace: WorkspaceStructureDependency,
    body: UpdateCustomFieldRequest,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    updated = await CustomFieldService().update(
        workspace.session,
        workspace.access,
        field_id,
        CustomFieldChanges(
            changed_fields=frozenset(body.model_fields_set),
            label=body.label,
            description=body.description,
            options=(None if body.options is None else tuple(o.to_option() for o in body.options)),
            display_condition=(
                None if body.display_condition is None else body.display_condition.to_condition()
            ),
            required_at_stage=body.required_at_stage,
            is_archived=body.is_archived,
            if_match=if_match,
        ),
    )
    return JSONResponse(content=_body(updated), headers=_headers(updated))
