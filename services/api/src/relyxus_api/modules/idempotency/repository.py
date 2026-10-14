import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.idempotency.model import IdempotencyRecord


class IdempotencyRepository:
    async def find_record(
        self, session: AsyncSession, organization_id: uuid.UUID, idempotency_key: str
    ) -> IdempotencyRecord | None:
        return await session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.organization_id == organization_id,
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )

    async def add_record(self, session: AsyncSession, record: IdempotencyRecord) -> IdempotencyRecord:
        session.add(record)
        await session.flush()
        return record
