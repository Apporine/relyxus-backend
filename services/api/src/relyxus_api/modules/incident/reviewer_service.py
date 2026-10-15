"""Required reviewers and sign-offs of a post-incident review (MPS-13.13, MPS-13.17).

The review owner (or a workspace owner) chooses who must sign off while the review is a
draft or in review; reviewers must be workspace members. A reviewer signs off while the
review is in review. Approval needs every required reviewer's sign-off, and SEV1/SEV2
reviews need at least one reviewer (register Q-38); sending the review back to draft
clears sign-offs. Those two rules live in the review service's transition.

Default reviewers: the incident commander is added when a SEV1/SEV2 review is created.
The spec's other defaults (service owner, Head of SRE, compliance officer when a clock
started, CISO for security events) need records that do not exist yet (Q-38).
"""

import uuid
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.role_requirements import InsufficientWorkspaceRoleError
from relyxus_api.modules.access.service import WorkspaceAccess, WorkspaceAccessService
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.review_model import (
    EDITABLE_REVIEW_STATES,
    IncidentReview,
    ReviewState,
)
from relyxus_api.modules.incident.review_repository import IncidentReviewRepository
from relyxus_api.modules.incident.review_service import REVIEW_SUBJECT_TYPE, ReviewNotFoundError
from relyxus_api.modules.incident.reviewer_model import (
    REVIEWER_ADDED_ACTION,
    REVIEWER_REMOVED_ACTION,
    SIGNED_OFF_ACTION,
    IncidentReviewReviewer,
)
from relyxus_api.modules.incident.reviewer_repository import (
    MAX_REVIEWERS,
    IncidentReviewerRepository,
)
from relyxus_api.modules.incident.service import IncidentNotFoundError
from relyxus_api.shared.errors.app_errors import ConflictError, NotFoundError, ValidationFailedError
from relyxus_api.shared.utils.ids import new_uuid7


class ReviewerNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_REVIEWER_NOT_FOUND"


class ReviewersLockedError(ConflictError):
    code: ClassVar[str] = "INCIDENT_REVIEW_NOT_EDITABLE"


class ReviewerNotMemberError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_REVIEWER_NOT_MEMBER"


class TooManyReviewersError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_REVIEW_TOO_MANY_REVIEWERS"


class NotAReviewerError(ConflictError):
    code: ClassVar[str] = "INCIDENT_REVIEW_NOT_A_REVIEWER"


class SignOffNotOpenError(ConflictError):
    code: ClassVar[str] = "INCIDENT_REVIEW_SIGN_OFF_NOT_OPEN"


class AlreadySignedOffError(ConflictError):
    code: ClassVar[str] = "INCIDENT_REVIEW_ALREADY_SIGNED_OFF"


class IncidentReviewerService:
    def __init__(
        self,
        reviewers: IncidentReviewerRepository | None = None,
        reviews: IncidentReviewRepository | None = None,
        incidents: IncidentRepository | None = None,
        access: WorkspaceAccessService | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._reviewers = reviewers or IncidentReviewerRepository()
        self._reviews = reviews or IncidentReviewRepository()
        self._incidents = incidents or IncidentRepository()
        self._access = access or WorkspaceAccessService(AccessRepository())
        self._activity = activity or IncidentActivityRecorder()

    async def list(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> list[IncidentReviewReviewer]:
        review = await self._review(session, access, incident_id, is_locking=False)
        return await self._reviewers.list_for_review(session, review.id)

    async def add(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> IncidentReviewReviewer:
        """Idempotent: adding someone already required returns the existing entry."""
        review = await self._review(session, access, incident_id, is_locking=True)
        _require_manager(access, review)
        existing = await self._reviewers.find(session, review.id, user_id)
        if existing is not None:
            return existing
        if not await self._access.is_workspace_member(session, user_id, access.workspace_id):
            raise ReviewerNotMemberError("Reviewers must be members of this workspace.")
        if len(await self._reviewers.list_for_review(session, review.id)) >= MAX_REVIEWERS:
            raise TooManyReviewersError(f"A review can have at most {MAX_REVIEWERS} reviewers.")
        reviewer = await self._reviewers.save(
            session,
            IncidentReviewReviewer(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                incident_id=review.incident_id,
                review_id=review.id,
                user_id=user_id,
                added_by_user_id=access.user_id,
            ),
        )
        await self._record(
            session, access, review, REVIEWER_ADDED_ACTION, None, {"user_id": str(user_id)}
        )
        return reviewer

    async def remove(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        review = await self._review(session, access, incident_id, is_locking=True)
        _require_manager(access, review)
        reviewer = await self._reviewers.find(session, review.id, user_id)
        if reviewer is None:
            raise ReviewerNotFoundError("This person is not a required reviewer.")
        await self._reviewers.remove(session, reviewer.id)
        await self._record(
            session, access, review, REVIEWER_REMOVED_ACTION, {"user_id": str(user_id)}, None
        )

    async def sign_off(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> IncidentReviewReviewer:
        review = await self._review(session, access, incident_id, is_locking=True)
        reviewer = await self._reviewers.find(session, review.id, access.user_id)
        if reviewer is None:
            raise NotAReviewerError("You are not a required reviewer of this review.")
        if ReviewState(review.state) is not ReviewState.IN_REVIEW:
            raise SignOffNotOpenError(f"Sign-off needs the review in review, not {review.state}.")
        if reviewer.signed_off_at is not None:
            raise AlreadySignedOffError("You have already signed off this review.")
        reviewer.signed_off_at = datetime.now(UTC)
        reviewer = await self._reviewers.save(session, reviewer)
        await self._record(
            session, access, review, SIGNED_OFF_ACTION, None, {"user_id": str(access.user_id)}
        )
        return reviewer

    async def _review(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        *,
        is_locking: bool,
    ) -> IncidentReview:
        if is_locking:
            incident = await self._incidents.lock_in_workspace(
                session, access.workspace_id, incident_id
            )
        else:
            incident = await self._incidents.find_in_workspace(
                session, access.workspace_id, incident_id
            )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        review = await self._reviews.find_for_incident(session, incident_id, is_locking=is_locking)
        if review is None:
            raise ReviewNotFoundError("This incident has no post-incident review yet.")
        return review

    async def _record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        review: IncidentReview,
        action: str,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
    ) -> None:
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=review.incident_id,
                action=action,
                subject_type=REVIEW_SUBJECT_TYPE,
                subject_id=review.id,
                before=before,
                after=after,
            ),
        )


def _require_manager(access: WorkspaceAccess, review: IncidentReview) -> None:
    if access.user_id != review.owner_user_id and WorkspaceRole.OWNER not in access.roles:
        raise InsufficientWorkspaceRoleError(
            "Only the review owner or a workspace owner can choose reviewers."
        )
    if ReviewState(review.state) not in EDITABLE_REVIEW_STATES:
        raise ReviewersLockedError(f"Reviewers of an {review.state} review are fixed.")
