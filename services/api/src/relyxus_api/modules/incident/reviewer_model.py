"""Required reviewers of a post-incident review and their sign-offs (MPS-13.13, 13.17).

A reviewer row means "this person must sign off"; `signed_off_at` is set when they do and
cleared when the review is sent back to draft, because its content may change.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns

REVIEWER_ADDED_ACTION = "incident.review_reviewer_added"
REVIEWER_REMOVED_ACTION = "incident.review_reviewer_removed"
SIGNED_OFF_ACTION = "incident.review_signed_off"


class IncidentReviewReviewer(RecordColumns, Base):
    __tablename__ = "incident_review_reviewers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["incident_id", "workspace_id"],
            ["incidents.id", "incidents.workspace_id"],
            name="fk_incident_review_reviewers_incident_same_workspace",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "review_id", "user_id", name="uq_incident_review_reviewers_review_id_user_id"
        ),
        Index("ix_incident_review_reviewers_organization_id", "organization_id"),
        Index("ix_incident_review_reviewers_workspace_id", "workspace_id"),
        Index("ix_incident_review_reviewers_incident_id", "incident_id"),
        Index("ix_incident_review_reviewers_user_id", "user_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[uuid.UUID]
    incident_id: Mapped[uuid.UUID]
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incident_reviews.id", ondelete="RESTRICT")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    added_by_user_id: Mapped[uuid.UUID]
    signed_off_at: Mapped[datetime | None]
