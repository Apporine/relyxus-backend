"""Service catalogue persistence. Queries only; rules live in the catalogue service."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.catalog.model import CatalogService


@dataclass(frozen=True, slots=True)
class ServiceListQuery:
    """Empty `tiers` means any tier."""

    owner_team_id: uuid.UUID | None
    tiers: frozenset[str]
    include_archived: bool


class CatalogRepository:
    async def save(self, session: AsyncSession, service: CatalogService) -> CatalogService:
        session.add(service)
        await session.flush()
        await session.refresh(service)
        return service

    async def find_by_key(
        self, session: AsyncSession, workspace_id: uuid.UUID, key: str
    ) -> CatalogService | None:
        service: CatalogService | None = await session.scalar(
            select(CatalogService).where(
                CatalogService.workspace_id == workspace_id, CatalogService.key == key
            )
        )
        return service

    async def find_in_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        service_id: uuid.UUID,
        *,
        is_locking: bool = False,
    ) -> CatalogService | None:
        query = select(CatalogService).where(
            CatalogService.id == service_id, CatalogService.workspace_id == workspace_id
        )
        if is_locking:
            query = query.with_for_update()
        service: CatalogService | None = await session.scalar(query)
        return service

    async def find_many_in_workspace(
        self, session: AsyncSession, workspace_id: uuid.UUID, service_ids: Collection[uuid.UUID]
    ) -> list[CatalogService]:
        services = await session.scalars(
            select(CatalogService).where(
                CatalogService.workspace_id == workspace_id, CatalogService.id.in_(service_ids)
            )
        )
        return list(services)

    async def list_in_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        filters: ServiceListQuery,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[CatalogService]:
        """Oldest first (UUIDv7 order), keyset page after `after_id`."""
        query = select(CatalogService).where(CatalogService.workspace_id == workspace_id)
        if filters.owner_team_id is not None:
            query = query.where(CatalogService.owner_team_id == filters.owner_team_id)
        if filters.tiers:
            query = query.where(CatalogService.tier.in_(filters.tiers))
        if not filters.include_archived:
            query = query.where(CatalogService.archived_at.is_(None))
        if after_id is not None:
            query = query.where(CatalogService.id > after_id)
        services = await session.scalars(query.order_by(CatalogService.id).limit(limit))
        return list(services)
