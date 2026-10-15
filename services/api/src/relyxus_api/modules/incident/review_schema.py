import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from relyxus_api.modules.incident.review_model import (
    REVIEW_TEXT_MAX_LENGTH,
    IncidentReview,
    ReviewState,
)
from relyxus_api.modules.incident.reviewer_model import IncidentReviewReviewer

ReviewText = Annotated[str, StringConstraints(max_length=REVIEW_TEXT_MAX_LENGTH)]


class UpdateReviewRequest(BaseModel):
    """Partial update. Content is editable while the review is a draft or in review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: ReviewText | None = Field(
        default=None, examples=["Card authorisations failed for 42 minutes in eu-west-1."]
    )
    lessons_learned: ReviewText | None = Field(
        default=None, description="Required to submit SEV1 and SEV2 reviews (MPS-13.16)."
    )
    owner_user_id: uuid.UUID | None = Field(
        default=None, description="Reassign the review; the new owner must be a member."
    )


class TransitionReviewRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_state: ReviewState = Field(
        description=(
            "`in_review` to submit, `draft` to send back, `approved`, then `published`. "
            "`closed` happens only when the incident closes."
        ),
        examples=[ReviewState.IN_REVIEW],
    )


class ReviewView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    state: ReviewState
    owner_user_id: uuid.UUID
    summary: str
    lessons_learned: str
    submitted_at: datetime | None
    approved_at: datetime | None
    published_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_review(cls, review: IncidentReview) -> "ReviewView":
        return cls(
            id=review.id,
            incident_id=review.incident_id,
            state=ReviewState(review.state),
            owner_user_id=review.owner_user_id,
            summary=review.summary,
            lessons_learned=review.lessons_learned,
            submitted_at=review.submitted_at,
            approved_at=review.approved_at,
            published_at=review.published_at,
            closed_at=review.closed_at,
            created_at=review.created_at,
            updated_at=review.updated_at,
        )


class ReviewerView(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: uuid.UUID
    added_by_user_id: uuid.UUID
    added_at: datetime
    signed_off_at: datetime | None = Field(
        description="Null until the reviewer signs off; cleared when the review is sent back."
    )

    @classmethod
    def from_reviewer(cls, reviewer: IncidentReviewReviewer) -> "ReviewerView":
        return cls(
            user_id=reviewer.user_id,
            added_by_user_id=reviewer.added_by_user_id,
            added_at=reviewer.created_at,
            signed_off_at=reviewer.signed_off_at,
        )
