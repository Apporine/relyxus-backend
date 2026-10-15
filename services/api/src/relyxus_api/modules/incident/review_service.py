"""Post-incident reviews (MPS-8A.11, MPS-13.12, MPS-13.16, MPS-20.50).

Created when the incident is resolved, owned by the incident commander at that moment
(or whoever resolved it when no commander is assigned). Incidents resolved before reviews
existed can get one through `start`.

States: Draft → In review → Approved → Published, and In review → Draft to send it back.
Each move is made by the review owner or a workspace owner. Submitting needs a summary,
and SEV1/SEV2 reviews need lessons learned (MPS-13.16). Summary and lessons can be edited
by incident writers while the review is a draft or in review; the owner can be changed by
the review owner, an incident commander or an owner. Closed is reached only by closing
the incident (MPS-8A.12). Every change is audited and on the timeline.

Not yet: required reviewers and sign-off before approval (MPS-13.13, next PR); due dates
and escalation (MPS-13.14); redaction and audiences (MPS-13.15); generated drafts (13.06).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.role_requirements import InsufficientWorkspaceRoleError
from relyxus_api.modules.access.service import WorkspaceAccess, WorkspaceAccessService
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.model import Incident, IncidentSeverity
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.review_model import (
    EDITABLE_REVIEW_STATES,
    IncidentReview,
    ReviewState,
)
from relyxus_api.modules.incident.review_repository import IncidentReviewRepository
from relyxus_api.modules.incident.role_model import IncidentRole
from relyxus_api.modules.incident.role_repository import IncidentRoleRepository
from relyxus_api.modules.incident.service import IncidentNotFoundError
from relyxus_api.shared.errors.app_errors import ConflictError, NotFoundError, ValidationFailedError
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.preconditions import assert_if_match
from relyxus_api.shared.utils.ids import new_uuid7

REVIEW_SUBJECT_TYPE = "incident_review"
REVIEW_CREATED_ACTION = "incident.review_created"
REVIEW_UPDATED_ACTION = "incident.review_updated"
REVIEW_TRANSITIONED_ACTION = "incident.review_transitioned"
LESSONS_REQUIRED_FOR = frozenset({IncidentSeverity.SEV1, IncidentSeverity.SEV2})
_OWNER_CHANGERS = frozenset({WorkspaceRole.INCIDENT_COMMANDER, WorkspaceRole.OWNER})
_REVIEW_MOVES: frozenset[tuple[ReviewState, ReviewState]] = frozenset(
    {
        (ReviewState.DRAFT, ReviewState.IN_REVIEW),
        (ReviewState.IN_REVIEW, ReviewState.DRAFT),
        (ReviewState.IN_REVIEW, ReviewState.APPROVED),
        (ReviewState.APPROVED, ReviewState.PUBLISHED),
    }
)
_POST_INCIDENT_STATES = frozenset({IncidentLifecycleState.RESOLVED, IncidentLifecycleState.CLOSED})


class ReviewNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_REVIEW_NOT_FOUND"


class ReviewAlreadyExistsError(ConflictError):
    code: ClassVar[str] = "INCIDENT_REVIEW_EXISTS"


class ReviewNotAvailableError(ConflictError):
    code: ClassVar[str] = "INCIDENT_REVIEW_NOT_AVAILABLE"


class ReviewNotEditableError(ConflictError):
    code: ClassVar[str] = "INCIDENT_REVIEW_NOT_EDITABLE"


class InvalidReviewTransitionError(ConflictError):
    code: ClassVar[str] = "INCIDENT_REVIEW_INVALID_TRANSITION"


class ReviewContentRequiredError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_REVIEW_CONTENT_REQUIRED"


class ReviewOwnerNotMemberError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_REVIEW_OWNER_NOT_MEMBER"


class NoReviewChangesError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_REVIEW_NO_CHANGES"


@dataclass(frozen=True, slots=True)
class ReviewChanges:
    summary: str | None = None
    lessons_learned: str | None = None
    owner_user_id: uuid.UUID | None = None
    if_match: str | None = None


class IncidentReviewService:
    def __init__(
        self,
        reviews: IncidentReviewRepository | None = None,
        incidents: IncidentRepository | None = None,
        roles: IncidentRoleRepository | None = None,
        access: WorkspaceAccessService | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._reviews = reviews or IncidentReviewRepository()
        self._incidents = incidents or IncidentRepository()
        self._roles = roles or IncidentRoleRepository()
        self._access = access or WorkspaceAccessService(AccessRepository())
        self._activity = activity or IncidentActivityRecorder()

    async def create_on_resolution(
        self, session: AsyncSession, access: WorkspaceAccess, incident: Incident
    ) -> IncidentReview | None:
        """Called by the resolve transition. A reopened-then-resolved incident keeps its
        existing review."""
        if await self._reviews.find_for_incident(session, incident.id) is not None:
            return None
        return await self._create(session, access, incident)

    async def start(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> IncidentReview:
        """For incidents resolved before reviews existed."""
        incident = await self._lock_incident(session, access, incident_id)
        if IncidentLifecycleState(incident.lifecycle_state) not in _POST_INCIDENT_STATES:
            raise ReviewNotAvailableError(
                "A post-incident review starts when the incident is resolved."
            )
        if await self._reviews.find_for_incident(session, incident_id) is not None:
            raise ReviewAlreadyExistsError("This incident already has a review.")
        return await self._create(session, access, incident)

    async def get(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> IncidentReview:
        incident = await self._incidents.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        review = await self._reviews.find_for_incident(session, incident_id)
        if review is None:
            raise ReviewNotFoundError("This incident has no post-incident review yet.")
        return review

    async def update(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        changes: ReviewChanges,
    ) -> IncidentReview:
        await self._lock_incident(session, access, incident_id)
        review = await self._lock_review(session, incident_id)
        assert_if_match(format_weak_etag(review.id, review.updated_at), changes.if_match)
        state = ReviewState(review.state)
        before: dict[str, object] = {}
        after: dict[str, object] = {}
        for name, new in (
            ("summary", changes.summary),
            ("lessons_learned", changes.lessons_learned),
        ):
            if new is None or new == getattr(review, name):
                continue
            if state not in EDITABLE_REVIEW_STATES:
                raise ReviewNotEditableError(f"An {state.value} review's content is locked.")
            before[name], after[name] = getattr(review, name), new
            setattr(review, name, new)
        new_owner = changes.owner_user_id
        if new_owner is not None and new_owner != review.owner_user_id:
            await self._change_owner(session, access, review, new_owner)
            before["owner_user_id"] = str(review.owner_user_id)
            after["owner_user_id"] = str(new_owner)
            review.owner_user_id = new_owner
        if not after:
            raise NoReviewChangesError("The request does not change the review.")
        review = await self._reviews.save(session, review)
        await self._record(session, access, review, REVIEW_UPDATED_ACTION, before, after)
        return review

    async def transition(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        target: ReviewState,
        if_match: str | None,
    ) -> IncidentReview:
        incident = await self._lock_incident(session, access, incident_id)
        review = await self._lock_review(session, incident_id)
        assert_if_match(format_weak_etag(review.id, review.updated_at), if_match)
        current = ReviewState(review.state)
        if (current, target) not in _REVIEW_MOVES:
            raise InvalidReviewTransitionError(
                f"A review cannot move from {current.value} to {target.value} this way."
            )
        if access.user_id != review.owner_user_id and WorkspaceRole.OWNER not in access.roles:
            raise InsufficientWorkspaceRoleError(
                "Only the review owner or a workspace owner can move the review."
            )
        now = datetime.now(UTC)
        if target is ReviewState.IN_REVIEW:
            _require_content(review, IncidentSeverity(incident.severity))
            review.submitted_at = now
        elif target is ReviewState.APPROVED:
            review.approved_at = now
        elif target is ReviewState.PUBLISHED:
            review.published_at = now
        review.state = target.value
        review = await self._reviews.save(session, review)
        await self._record(
            session,
            access,
            review,
            REVIEW_TRANSITIONED_ACTION,
            {"state": current.value},
            {"state": target.value},
        )
        return review

    async def _create(
        self, session: AsyncSession, access: WorkspaceAccess, incident: Incident
    ) -> IncidentReview:
        commander = await self._roles.find(
            session, incident.id, IncidentRole.INCIDENT_COMMANDER.value
        )
        review = await self._reviews.save(
            session,
            IncidentReview(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                incident_id=incident.id,
                state=ReviewState.DRAFT.value,
                owner_user_id=access.user_id if commander is None else commander.user_id,
                summary="",
                lessons_learned="",
            ),
        )
        await self._record(
            session,
            access,
            review,
            REVIEW_CREATED_ACTION,
            None,
            {"state": review.state, "owner_user_id": str(review.owner_user_id)},
        )
        return review

    async def _change_owner(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        review: IncidentReview,
        new_owner: uuid.UUID,
    ) -> None:
        if ReviewState(review.state) is ReviewState.CLOSED:
            raise ReviewNotEditableError("A closed review can no longer change.")
        if access.user_id != review.owner_user_id and not _OWNER_CHANGERS.intersection(
            access.roles
        ):
            raise InsufficientWorkspaceRoleError(
                "Only the review owner, an incident commander or an owner can reassign a review."
            )
        if not await self._access.is_workspace_member(session, new_owner, access.workspace_id):
            raise ReviewOwnerNotMemberError("The review owner must be a member of this workspace.")

    async def _lock_incident(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> Incident:
        incident = await self._incidents.lock_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        return incident

    async def _lock_review(self, session: AsyncSession, incident_id: uuid.UUID) -> IncidentReview:
        review = await self._reviews.find_for_incident(session, incident_id, is_locking=True)
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
        after: dict[str, object],
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


def _require_content(review: IncidentReview, severity: IncidentSeverity) -> None:
    if not review.summary.strip():
        raise ReviewContentRequiredError("Write a summary before submitting the review.")
    if severity in LESSONS_REQUIRED_FOR and not review.lessons_learned.strip():
        raise ReviewContentRequiredError(
            f"Lessons learned are required for {severity.value.upper()} reviews (MPS-13.16)."
        )
