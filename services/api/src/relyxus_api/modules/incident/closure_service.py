"""The closure gate: Resolved → Closed (MPS-8A.12, MPS-13.04, MPS-13.17).

Who: the review owner, or a workspace owner (who "can do everything", MPS-14.02).

What must hold, checked in this order:
1. The post-incident review is approved or published, so its required reviewers have
   signed off (MPS-8A.12, MPS-13.17).
2. No live task is still open, in progress or blocked: at resolution each became a
   follow-up or was finished or cancelled (MPS-11.21; enforcing it here is register Q-39).
3. SEV1/SEV2: every unfinished mandatory follow-up has an owner and a due date (13.17).
4. SEV1/SEV2: a root cause is recorded (MPS-13.04, free text until the Brain's ranked
   hypotheses exist).

An authorised exception with a reason skips 1-3 (MPS-13.17); only a workspace owner may
record one (Q-39). The root cause is still required. Closing locks the review (Closed)
and records everything on the timeline and in the audit chain.

Not yet: report lock and analytics update (8A.12) beyond the review state, because
reports and analytics do not exist yet.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.access.role_requirements import InsufficientWorkspaceRoleError
from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.follow_up_model import FollowUpStatus
from relyxus_api.modules.incident.follow_up_repository import IncidentFollowUpRepository
from relyxus_api.modules.incident.model import Incident, IncidentSeverity
from relyxus_api.modules.incident.review_model import IncidentReview, ReviewState
from relyxus_api.modules.incident.review_repository import IncidentReviewRepository
from relyxus_api.modules.incident.review_service import (
    REVIEW_SUBJECT_TYPE,
    REVIEW_TRANSITIONED_ACTION,
)
from relyxus_api.modules.incident.task_model import TaskStatus
from relyxus_api.modules.incident.task_repository import IncidentTaskRepository
from relyxus_api.shared.errors.app_errors import ConflictError, ValidationFailedError

STRICT_CLOSURE_SEVERITIES = frozenset({IncidentSeverity.SEV1, IncidentSeverity.SEV2})
_SIGNED_OFF_REVIEW_STATES = frozenset({ReviewState.APPROVED, ReviewState.PUBLISHED})
_UNFINISHED_TASKS = [TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED]
_UNFINISHED_FOLLOW_UPS = [FollowUpStatus.OPEN, FollowUpStatus.IN_PROGRESS]
_LISTED_IDS = 10


class IncidentReviewRequiredError(ConflictError):
    code: ClassVar[str] = "INCIDENT_REVIEW_REQUIRED"


class UnfinishedTasksError(ConflictError):
    code: ClassVar[str] = "INCIDENT_UNFINISHED_TASKS"


class IncompleteFollowUpsError(ConflictError):
    code: ClassVar[str] = "INCIDENT_FOLLOW_UPS_INCOMPLETE"


class RootCauseRequiredError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_ROOT_CAUSE_REQUIRED"


@dataclass(frozen=True, slots=True)
class ClosureDetails:
    root_cause: str | None
    exception_reason: str | None


class IncidentClosureService:
    def __init__(
        self,
        reviews: IncidentReviewRepository | None = None,
        tasks: IncidentTaskRepository | None = None,
        follow_ups: IncidentFollowUpRepository | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._reviews = reviews or IncidentReviewRepository()
        self._tasks = tasks or IncidentTaskRepository()
        self._follow_ups = follow_ups or IncidentFollowUpRepository()
        self._activity = activity or IncidentActivityRecorder()

    async def check(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident: Incident,
        details: ClosureDetails,
    ) -> IncidentReview | None:
        """Raise unless the caller may close the incident now; returns its review."""
        review = await self._reviews.find_for_incident(session, incident.id, is_locking=True)
        is_workspace_owner = WorkspaceRole.OWNER in access.roles
        is_review_owner = review is not None and review.owner_user_id == access.user_id
        if not (is_review_owner or is_workspace_owner):
            raise InsufficientWorkspaceRoleError(
                "Only the post-incident review owner or a workspace owner can close an incident."
            )
        if details.exception_reason and not is_workspace_owner:
            raise InsufficientWorkspaceRoleError(
                "Only a workspace owner can record a closure exception."
            )
        severity = IncidentSeverity(incident.severity)
        if not details.exception_reason:
            await self._check_gates(session, incident, review, severity)
        if severity in STRICT_CLOSURE_SEVERITIES and not details.root_cause:
            raise RootCauseRequiredError(
                f"A root cause is required to close a {severity.value.upper()} incident."
            )
        return review

    async def lock_review(
        self, session: AsyncSession, access: WorkspaceAccess, review: IncidentReview | None
    ) -> None:
        """After closing: a signed-off review becomes Closed (MPS-8A.12 report lock)."""
        if review is None or ReviewState(review.state) not in _SIGNED_OFF_REVIEW_STATES:
            return
        before = review.state
        review.state = ReviewState.CLOSED.value
        review.closed_at = datetime.now(UTC)
        review = await self._reviews.save(session, review)
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=review.incident_id,
                action=REVIEW_TRANSITIONED_ACTION,
                subject_type=REVIEW_SUBJECT_TYPE,
                subject_id=review.id,
                before={"state": before},
                after={"state": review.state},
            ),
        )

    async def _check_gates(
        self,
        session: AsyncSession,
        incident: Incident,
        review: IncidentReview | None,
        severity: IncidentSeverity,
    ) -> None:
        if review is None or ReviewState(review.state) not in _SIGNED_OFF_REVIEW_STATES:
            raise IncidentReviewRequiredError(
                "Closing requires the post-incident review to be approved by its reviewers."
            )
        tasks = await self._tasks.list_unfinished_for_incident(
            session, incident.id, [status.value for status in _UNFINISHED_TASKS], _LISTED_IDS
        )
        if tasks:
            raise UnfinishedTasksError(
                "Move unfinished live tasks to follow-ups or finish or cancel them first: "
                + ", ".join(str(task.id) for task in tasks)
            )
        if severity not in STRICT_CLOSURE_SEVERITIES:
            return
        follow_ups = await self._follow_ups.list_incomplete_mandatory(
            session,
            incident.id,
            [status.value for status in _UNFINISHED_FOLLOW_UPS],
            _LISTED_IDS,
        )
        if follow_ups:
            raise IncompleteFollowUpsError(
                "Every mandatory follow-up needs an owner and a due date: "
                + ", ".join(str(follow_up.id) for follow_up in follow_ups)
            )
