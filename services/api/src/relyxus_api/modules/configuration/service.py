"""Record and read configuration versions (MPS-14A.07, MPS-20.29, MPS-8A.06).

Configuration services call `record` in the same transaction as the change, after
locking the object, so version numbers are gap-free per object and a change can never
commit without its version. The difference holds only the fields that changed.

Not yet: rolling back to an earlier version (MPS-14A.07 "non-destructive changes can be
rolled back"), Terraform as a source, drift detection (MPS-14A.06).
"""

import uuid
from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.configuration.model import (
    ConfigurationObjectType,
    ConfigurationSource,
    ConfigurationVersion,
)
from relyxus_api.modules.configuration.repository import ConfigurationVersionRepository
from relyxus_api.shared.errors.app_errors import NotFoundError
from relyxus_api.shared.http.pagination import InvalidCursorError, Page, PageRequest, build_page
from relyxus_api.shared.utils.ids import new_uuid7


class ConfigurationVersionNotFoundError(NotFoundError):
    code: ClassVar[str] = "CONFIGURATION_VERSION_NOT_FOUND"


@dataclass(frozen=True, slots=True)
class ConfigurationChange:
    object_type: ConfigurationObjectType
    object_id: uuid.UUID
    before: dict[str, object] | None
    after: dict[str, object]


class ConfigurationVersionService:
    def __init__(self, repository: ConfigurationVersionRepository | None = None) -> None:
        self._repository = repository or ConfigurationVersionRepository()

    async def record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        change: ConfigurationChange,
        source: ConfigurationSource = ConfigurationSource.API,
    ) -> ConfigurationVersion:
        latest = await self._repository.latest_version_number(
            session, change.object_type.value, change.object_id
        )
        return await self._repository.append(
            session,
            ConfigurationVersion(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                object_type=change.object_type.value,
                object_id=change.object_id,
                version=latest + 1,
                source=source.value,
                actor_user_id=access.user_id,
                snapshot=dict(change.after),
                difference=_difference(change.before, change.after),
            ),
        )

    async def get(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        object_type: ConfigurationObjectType,
        object_id: uuid.UUID,
        version: int,
    ) -> ConfigurationVersion:
        found = await self._repository.find(
            session, access.workspace_id, object_type.value, object_id, version
        )
        if found is None:
            raise ConfigurationVersionNotFoundError("No such configuration version.")
        return found

    async def list(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        object_type: ConfigurationObjectType,
        object_id: uuid.UUID,
        page_request: PageRequest,
    ) -> Page[ConfigurationVersion]:
        fetched = await self._repository.list_for_object(
            session,
            access.workspace_id,
            object_type.value,
            object_id,
            _decode_cursor(page_request),
            page_request.limit + 1,
        )
        return build_page(fetched, page_request, lambda version: (version.version,))


def _difference(before: dict[str, object] | None, after: dict[str, object]) -> dict[str, object]:
    """`{field: {"before": old, "after": new}}` for changed fields; everything on creation."""
    previous = before or {}
    keys = sorted(set(previous) | set(after))
    return {
        key: {"before": previous.get(key), "after": after.get(key)}
        for key in keys
        if before is None or previous.get(key) != after.get(key)
    }


def _decode_cursor(page_request: PageRequest) -> int | None:
    if page_request.after is None:
        return None
    position = page_request.after
    if len(position) != 1 or not isinstance(position[0], int) or position[0] < 1:
        raise InvalidCursorError("The cursor is not valid; restart from the first page.")
    return position[0]
