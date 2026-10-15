"""Configuration version persistence. Append and read only; rows are immutable."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.configuration.model import ConfigurationVersion


class ConfigurationVersionRepository:
    async def append(
        self, session: AsyncSession, version: ConfigurationVersion
    ) -> ConfigurationVersion:
        session.add(version)
        await session.flush()
        await session.refresh(version)
        return version

    async def latest_version_number(
        self, session: AsyncSession, object_type: str, object_id: uuid.UUID
    ) -> int:
        latest = await session.scalar(
            select(func.max(ConfigurationVersion.version)).where(
                ConfigurationVersion.object_type == object_type,
                ConfigurationVersion.object_id == object_id,
            )
        )
        return int(latest or 0)

    async def find(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        object_type: str,
        object_id: uuid.UUID,
        version: int,
    ) -> ConfigurationVersion | None:
        found: ConfigurationVersion | None = await session.scalar(
            select(ConfigurationVersion).where(
                ConfigurationVersion.workspace_id == workspace_id,
                ConfigurationVersion.object_type == object_type,
                ConfigurationVersion.object_id == object_id,
                ConfigurationVersion.version == version,
            )
        )
        return found

    async def list_for_object(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        object_type: str,
        object_id: uuid.UUID,
        after_version: int | None,
        limit: int,
    ) -> list[ConfigurationVersion]:
        """Oldest first, keyset page after `after_version`."""
        query = select(ConfigurationVersion).where(
            ConfigurationVersion.workspace_id == workspace_id,
            ConfigurationVersion.object_type == object_type,
            ConfigurationVersion.object_id == object_id,
        )
        if after_version is not None:
            query = query.where(ConfigurationVersion.version > after_version)
        versions = await session.scalars(query.order_by(ConfigurationVersion.version).limit(limit))
        return list(versions)
