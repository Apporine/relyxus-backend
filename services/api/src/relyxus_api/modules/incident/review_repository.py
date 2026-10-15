"""Post-incident review persistence. Queries only; rules live in the review service."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.review_model import IncidentReview


class IncidentReviewRepository:
    async def save(self, session: AsyncSession, review: IncidentReview) -> IncidentReview:
        session.add(review)
        await session.flush()
        await session.refresh(review)
        return review

    async def find_for_incident(
        self, session: AsyncSession, incident_id: uuid.UUID, *, is_locking: bool = False
    ) -> IncidentReview | None:
        query = select(IncidentReview).where(IncidentReview.incident_id == incident_id)
        if is_locking:
            query = query.with_for_update()
        review: IncidentReview | None = await session.scalar(query)
        return review
