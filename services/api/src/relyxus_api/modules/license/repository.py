import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.license.model import OrganizationLicense


class LicenseRepository:
    async def find_current(
        self, session: AsyncSession, organization_id: uuid.UUID
    ) -> OrganizationLicense | None:
        return await session.scalar(
            select(OrganizationLicense).where(
                OrganizationLicense.organization_id == organization_id,
                OrganizationLicense.is_current.is_(True),
            )
        )

    async def supersede_current(
        self, session: AsyncSession, organization_id: uuid.UUID, when: datetime
    ) -> None:
        await session.execute(
            update(OrganizationLicense)
            .where(
                OrganizationLicense.organization_id == organization_id,
                OrganizationLicense.is_current.is_(True),
            )
            .values(is_current=False, superseded_at=when)
        )

    async def add_record(
        self, session: AsyncSession, record: OrganizationLicense
    ) -> OrganizationLicense:
        session.add(record)
        await session.flush()
        return record

    async def mark_superseded_now(
        self, session: AsyncSession, organization_id: uuid.UUID
    ) -> None:
        await self.supersede_current(session, organization_id, datetime.now(UTC))
