import uuid

from fastapi import APIRouter

from relyxus_api.modules.access.dependencies import WorkspaceSessionDependency
from relyxus_api.modules.configuration.model import ConfigurationObjectType
from relyxus_api.modules.configuration.schema import ConfigurationVersionView
from relyxus_api.modules.configuration.service import ConfigurationVersionService
from relyxus_api.shared.http.envelope import ListEnvelope, SuccessEnvelope, wrap_page, wrap_success
from relyxus_api.shared.http.pagination import Page, PageRequestDependency

CONFIGURATION_TAG = "configuration"
VERSIONS_PATH = "/configuration/{object_type}/{object_id}/versions"

router = APIRouter(prefix="/api/v1", tags=[CONFIGURATION_TAG])


@router.get(
    VERSIONS_PATH,
    summary="List a configuration object's versions",
    description=(
        "Every change to a team, service, incident type or custom field, oldest first "
        "(MPS-14A.07): who, when, source, full state and exact difference. Versions are "
        "immutable. Cursor-paginated; no total."
    ),
    response_model=ListEnvelope[ConfigurationVersionView],
)
async def list_configuration_versions(
    object_type: ConfigurationObjectType,
    object_id: uuid.UUID,
    workspace: WorkspaceSessionDependency,
    page_request: PageRequestDependency,
) -> ListEnvelope[ConfigurationVersionView]:
    page = await ConfigurationVersionService().list(
        workspace.session, workspace.access, object_type, object_id, page_request
    )
    views = [ConfigurationVersionView.from_version(version) for version in page.items]
    return wrap_page(Page(items=views, next_cursor=page.next_cursor, limit=page.limit))


@router.get(
    f"{VERSIONS_PATH}/{{version}}",
    summary="Get one configuration version",
    description="404 `CONFIGURATION_VERSION_NOT_FOUND` for unknown objects or versions.",
    response_model=SuccessEnvelope[ConfigurationVersionView],
)
async def get_configuration_version(
    object_type: ConfigurationObjectType,
    object_id: uuid.UUID,
    version: int,
    workspace: WorkspaceSessionDependency,
) -> SuccessEnvelope[ConfigurationVersionView]:
    found = await ConfigurationVersionService().get(
        workspace.session, workspace.access, object_type, object_id, version
    )
    return wrap_success(ConfigurationVersionView.from_version(found))
