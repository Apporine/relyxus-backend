"""Post-incident reviews (MPS-13.12, MPS-13.16, MPS-20.50; post-mortem ≡ review, MPS-26.02).

One review per incident, created when the incident is resolved (MPS-8A.11). The review
owner moves it Draft → In review → Approved → Published; it becomes Closed with the
incident (MPS-8A.12).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns

REVIEW_TEXT_MAX_LENGTH = 20000


class ReviewState(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    CLOSED = "closed"


EDITABLE_REVIEW_STATES = frozenset({ReviewState.DRAFT, ReviewState.IN_REVIEW})

_STATES_SQL = ", ".join(f"'{state.value}'" for state in ReviewState)


class IncidentReview(RecordColumns, Base):
    __tablename__ = "incident_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_reviews_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        CheckConstraint(f"state IN ({_STATES_SQL})", name="state"),
        CheckConstraint(
            f"char_length(summary) <= {REVIEW_TEXT_MAX_LENGTH}"
            f" AND char_length(lessons_learned) <= {REVIEW_TEXT_MAX_LENGTH}",
            name="text_length",
        ),
        Index("ix_incident_reviews_organization_id", "organization_id"),
        Index("ix_incident_reviews_workspace_id", "workspace_id"),
        Index("ix_incident_reviews_owner_user_id", "owner_user_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    incident_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    state: Mapped[str] = mapped_column(String(16))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    lessons_learned: Mapped[str] = mapped_column(Text, default="", server_default="")
    submitted_at: Mapped[datetime | None]
    approved_at: Mapped[datetime | None]
    published_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
