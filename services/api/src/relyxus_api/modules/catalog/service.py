"""The service catalogue (MPS-14.01, MPS-20.08).

Owners and admins add and change services; every workspace member reads them. A
service's key is its stable identifier and never changes. The owner team, if set, must
belong to the same workspace. Archiving keeps the record and its values; archived
services are hidden from lists unless asked for. Every change is audited.

Not yet: SLOs, dependencies (MPS-20.09), business services (MPS-20.10), catalogue import
and source priority (MPS-7.24).
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.audit.model import ActorType, AuditOutcome
from relyxus_api.modules.audit.service import AuditService, NewAuditEvent
from relyxus_api.modules.catalog.model import CatalogService, ServiceTier
from relyxus_api.modules.catalog.repository import CatalogRepository, ServiceListQuery
from relyxus_api.modules.team.repository import TeamRepository
from relyxus_api.shared.errors.app_errors import ConflictError, NotFoundError, ValidationFailedError
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.id_cursor import decode_id_cursor
from relyxus_api.shared.http.pagination import Page, PageRequest, build_page
from relyxus_api.shared.http.preconditions import assert_if_match
from relyxus_api.shared.observability.correlation import get_correlation_id
from relyxus_api.shared.utils.ids import new_uuid7

SERVICE_TARGET_TYPE = "service"
SERVICE_CREATED_ACTION = "service.created"
SERVICE_UPDATED_ACTION = "service.updated"


class ServiceNotFoundError(NotFoundError):
    code: ClassVar[str] = "SERVICE_NOT_FOUND"


class ServiceKeyTakenError(ConflictError):
    code: ClassVar[str] = "SERVICE_KEY_TAKEN"


class OwnerTeamNotFoundError(ValidationFailedError):
    code: ClassVar[str] = "SERVICE_OWNER_TEAM_NOT_FOUND"


class NoServiceChangesError(ValidationFailedError):
    code: ClassVar[str] = "SERVICE_NO_CHANGES"


@dataclass(frozen=True, slots=True)
class NewCatalogService:
    key: str
    name: str
    description: str | None
    tier: ServiceTier
    environment: str
    owner_team_id: uuid.UUID | None
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CatalogServiceChanges:
    """`changed_fields` says which fields were sent, so null can clear optional ones."""

    changed_fields: frozenset[str]
    name: str | None = None
    description: str | None = None
    tier: ServiceTier | None = None
    environment: str | None = None
    owner_team_id: uuid.UUID | None = None
    labels: dict[str, str] | None = None
    is_archived: bool | None = None
    if_match: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogFilters:
    owner_team_id: uuid.UUID | None = None
    tiers: frozenset[ServiceTier] = frozenset()
    include_archived: bool = False


class ServiceCatalog:
    def __init__(
        self,
        repository: CatalogRepository | None = None,
        teams: TeamRepository | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._repository = repository or CatalogRepository()
        self._teams = teams or TeamRepository()
        self._audit = audit or AuditService()

    async def create(
        self, session: AsyncSession, access: WorkspaceAccess, new_service: NewCatalogService
    ) -> CatalogService:
        if await self._repository.find_by_key(session, access.workspace_id, new_service.key):
            raise ServiceKeyTakenError(f"A service with the key '{new_service.key}' exists.")
        await self._require_team(session, access, new_service.owner_team_id)
        service = await self._repository.save(
            session,
            CatalogService(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                key=new_service.key,
                name=new_service.name,
                description=new_service.description,
                tier=new_service.tier.value,
                environment=new_service.environment,
                owner_team_id=new_service.owner_team_id,
                labels=dict(new_service.labels),
            ),
        )
        await self._record(
            session, access, service.id, SERVICE_CREATED_ACTION, None, _snapshot(service)
        )
        return service

    async def get(
        self, session: AsyncSession, access: WorkspaceAccess, service_id: uuid.UUID
    ) -> CatalogService:
        service = await self._repository.find_in_workspace(session, access.workspace_id, service_id)
        if service is None:
            raise ServiceNotFoundError("No service with this ID exists in this workspace.")
        return service

    async def list(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        filters: CatalogFilters,
        page_request: PageRequest,
    ) -> Page[CatalogService]:
        fetched = await self._repository.list_in_workspace(
            session,
            access.workspace_id,
            ServiceListQuery(
                owner_team_id=filters.owner_team_id,
                tiers=frozenset(tier.value for tier in filters.tiers),
                include_archived=filters.include_archived,
            ),
            decode_id_cursor(page_request),
            page_request.limit + 1,
        )
        return build_page(fetched, page_request, lambda service: (str(service.id),))

    async def update(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        service_id: uuid.UUID,
        changes: CatalogServiceChanges,
    ) -> CatalogService:
        service = await self._repository.find_in_workspace(
            session, access.workspace_id, service_id, is_locking=True
        )
        if service is None:
            raise ServiceNotFoundError("No service with this ID exists in this workspace.")
        assert_if_match(format_weak_etag(service.id, service.updated_at), changes.if_match)
        fields = changes.changed_fields
        if "owner_team_id" in fields:
            await self._require_team(session, access, changes.owner_team_id)
        before = _snapshot(service)
        _apply(service, changes)
        after = _snapshot(service)
        changed = sorted(key for key in after if after[key] != before[key])
        if not changed:
            raise NoServiceChangesError("The request does not change the service.")
        service = await self._repository.save(session, service)
        await self._record(
            session,
            access,
            service.id,
            SERVICE_UPDATED_ACTION,
            {key: before[key] for key in changed},
            {key: after[key] for key in changed},
        )
        return service

    async def _require_team(
        self, session: AsyncSession, access: WorkspaceAccess, team_id: uuid.UUID | None
    ) -> None:
        if team_id is not None and not await self._teams.find_in_workspace(
            session, access.workspace_id, team_id
        ):
            raise OwnerTeamNotFoundError("The owner team must be a team of this workspace.")

    async def _record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        service_id: uuid.UUID,
        action: str,
        before: dict[str, object] | None,
        after: dict[str, object],
    ) -> None:
        await self._audit.append(
            session,
            NewAuditEvent(
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                actor_type=ActorType.USER,
                actor_user_id=access.user_id,
                effective_user_id=None,
                action=action,
                target_type=SERVICE_TARGET_TYPE,
                target_id=str(service_id),
                outcome=AuditOutcome.SUCCEEDED,
                before_state=before,
                after_state=after,
                correlation_id=get_correlation_id(),
            ),
        )


def _apply(service: CatalogService, changes: CatalogServiceChanges) -> None:
    fields = changes.changed_fields
    if "name" in fields and changes.name is not None:
        service.name = changes.name
    if "description" in fields:
        service.description = changes.description
    if "tier" in fields and changes.tier is not None:
        service.tier = changes.tier.value
    if "environment" in fields and changes.environment is not None:
        service.environment = changes.environment
    if "owner_team_id" in fields:
        service.owner_team_id = changes.owner_team_id
    if "labels" in fields and changes.labels is not None:
        service.labels = dict(changes.labels)
    if "is_archived" in fields and changes.is_archived is not None:
        is_archived = service.archived_at is not None
        if changes.is_archived and not is_archived:
            service.archived_at = datetime.now(UTC)
        elif not changes.is_archived and is_archived:
            service.archived_at = None


def _snapshot(service: CatalogService) -> dict[str, object]:
    return {
        "key": service.key,
        "name": service.name,
        "description": service.description,
        "tier": service.tier,
        "environment": service.environment,
        "owner_team_id": None if service.owner_team_id is None else str(service.owner_team_id),
        "labels": dict(service.labels),
        "is_archived": service.archived_at is not None,
    }
