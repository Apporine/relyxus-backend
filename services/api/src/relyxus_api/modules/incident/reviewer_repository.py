"""Review reviewer persistence. Queries only; rules live in the services."""

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.incident.reviewer_model import IncidentReviewReviewer

# Bound on reviewers per review; far above any realistic sign-off list.
MAX_REVIEWERS = 50


class IncidentReviewerRepository:
    async def save(
        self, session: AsyncSession, reviewer: IncidentReviewReviewer
    ) -> IncidentReviewReviewer:
        session.add(reviewer)
        await session.flush()
        await session.refresh(reviewer)
        return reviewer

    async def find(
        self, session: AsyncSession, review_id: uuid.UUID, user_id: uuid.UUID
    ) -> IncidentReviewReviewer | None:
        reviewer: IncidentReviewReviewer | None = await session.scalar(
            select(IncidentReviewReviewer).where(
                IncidentReviewReviewer.review_id == review_id,
                IncidentReviewReviewer.user_id == user_id,
            )
        )
        return reviewer

    async def list_for_review(
        self, session: AsyncSession, review_id: uuid.UUID
    ) -> list[IncidentReviewReviewer]:
        """Oldest first, at most MAX_REVIEWERS (enforced when adding)."""
        reviewers = await session.scalars(
            select(IncidentReviewReviewer)
            .where(IncidentReviewReviewer.review_id == review_id)
            .order_by(IncidentReviewReviewer.id)
            .limit(MAX_REVIEWERS)
        )
        return list(reviewers)

    async def remove(self, session: AsyncSession, reviewer_id: uuid.UUID) -> None:
        await session.execute(
            delete(IncidentReviewReviewer).where(IncidentReviewReviewer.id == reviewer_id)
        )

    async def clear_sign_offs(self, session: AsyncSession, review_id: uuid.UUID) -> None:
        await session.execute(
            update(IncidentReviewReviewer)
            .where(IncidentReviewReviewer.review_id == review_id)
            .values(signed_off_at=None)
        )
