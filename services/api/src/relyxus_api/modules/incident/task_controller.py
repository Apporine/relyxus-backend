import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from relyxus_api.modules.access.dependencies import WorkspaceSessionDependency
from relyxus_api.modules.access.role_requirements import IncidentWriteWorkspaceDependency
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.incident.task_model import IncidentTask
from relyxus_api.modules.incident.task_schema import CreateTaskRequest, TaskView, UpdateTaskRequest
from relyxus_api.modules.incident.task_service import IncidentTaskService, NewTask, TaskChanges
from relyxus_api.shared.constants import IDEMPOTENCY_HEADER
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

TASKS_TAG = "incident-tasks"
CREATED_STATUS = 201

router = APIRouter(prefix="/api/v1", tags=[TASKS_TAG])


def _task_response(task: IncidentTask, status_code: int = 200) -> JSONResponse:
    body = wrap_success(TaskView.from_task(task)).model_dump(mode="json")
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={"ETag": format_weak_etag(task.id, task.updated_at)},
    )


@router.post(
    "/incidents/{incident_id}/tasks",
    summary="Create a live task on an incident",
    description=(
        "Adds a task to an open incident (MPS-11.14). The owner, if given, must be a member of "
        f"this workspace. Requires `{IDEMPOTENCY_HEADER}` and an incident-writing role."
    ),
    response_model=SuccessEnvelope[TaskView],
    status_code=CREATED_STATUS,
)
async def create_task(
    request: Request,
    incident_id: uuid.UUID,
    workspace: IncidentWriteWorkspaceDependency,
    body: CreateTaskRequest,
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

    task = await IncidentTaskService().create(
        workspace.session,
        workspace.access,
        incident_id,
        NewTask(
            title=body.title,
            priority=body.priority,
            owner_user_id=body.owner_user_id,
            due_at=body.due_at,
        ),
    )
    response = _task_response(task, CREATED_STATUS)
    await idempotency.complete(
        workspace.session,
        reservation.record_id,
        status_code=CREATED_STATUS,
        body=wrap_success(TaskView.from_task(task)).model_dump(mode="json"),
    )
    return response


@router.get(
    "/incidents/{incident_id}/tasks",
    summary="List an incident's tasks",
    description="Oldest first, cursor-paginated; no total. Visibility follows the incident.",
    response_model=ListEnvelope[TaskView],
)
async def list_tasks(
    incident_id: uuid.UUID,
    workspace: WorkspaceSessionDependency,
    page_request: PageRequestDependency,
) -> ListEnvelope[TaskView]:
    page = await IncidentTaskService().list(
        workspace.session, workspace.access, incident_id, page_request
    )
    views = [TaskView.from_task(task) for task in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))


@router.patch(
    "/incidents/{incident_id}/tasks/{task_id}",
    summary="Update a task",
    description=(
        "Change title, priority, owner, due time or status. Cancelling needs a `reason`; done "
        "and cancelled tasks are final. Send `owner_user_id` or `due_at` as null to clear "
        "them. Optional `If-Match` returns 412 when the task changed since it was read."
    ),
    response_model=SuccessEnvelope[TaskView],
)
async def update_task(
    incident_id: uuid.UUID,
    task_id: uuid.UUID,
    workspace: IncidentWriteWorkspaceDependency,
    body: UpdateTaskRequest,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    task = await IncidentTaskService().update(
        workspace.session,
        workspace.access,
        incident_id,
        task_id,
        TaskChanges(
            changed_fields=frozenset(body.model_fields_set),
            title=body.title,
            priority=body.priority,
            owner_user_id=body.owner_user_id,
            due_at=body.due_at,
            status=body.status,
            reason=body.reason,
            if_match=if_match,
        ),
    )
    return _task_response(task)
