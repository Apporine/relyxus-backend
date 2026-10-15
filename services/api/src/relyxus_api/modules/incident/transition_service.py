"""Incident lifecycle transitions (MPS-8A.09-8A.17, MPS-8A.20, MPS-8A.22; ADR-0004).

Each transition locks the incident row, checks the optional ETag, the lifecycle graph, the
caller's role and the transition's own rules, updates the metric timestamps, and records
the change in the audit chain and the timeline in the same transaction.

Not yet enforceable (their records do not exist yet; tracked in the PR and ADR-0004):
a working hypothesis or action before mitigating (8A.09), a mitigation action before
monitoring (8A.10), impact back to normal for the watch period before resolving (8A.11).
Closing is refused until post-incident review sign-off exists (8A.12, MPS-13.17).
Resolving creates the post-incident review (8A.11).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.role_requirements import InsufficientWorkspaceRoleError
from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.lifecycle import (
    OPEN_LIFECYCLE_STATES,
    IncidentLifecycleState,
    validate_lifecycle_transition,
)
from relyxus_api.modules.incident.model import Incident
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.review_service import IncidentReviewService
from relyxus_api.modules.incident.service import INCIDENT_TARGET_TYPE, IncidentNotFoundError
from relyxus_api.modules.incident.transition_rules import roles_allowed_for
from relyxus_api.shared.errors.app_errors import ConflictError, ValidationFailedError
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.preconditions import assert_if_match

TRANSITIONED_ACTION = "incident.transitioned"
_STATE = IncidentLifecycleState
_REASON_REQUIRED_FOR = frozenset({_STATE.CANCELLED})


class IncidentAlreadyInStateError(ConflictError):
    code: ClassVar[str] = "INCIDENT_ALREADY_IN_STATE"


class IncidentReviewRequiredError(ConflictError):
    code: ClassVar[str] = "INCIDENT_REVIEW_REQUIRED"


class IncidentReopenWindowExpiredError(ConflictError):
    code: ClassVar[str] = "INCIDENT_REOPEN_WINDOW_EXPIRED"


class InvalidMergeTargetError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_INVALID_MERGE_TARGET"


class TransitionReasonRequiredError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_TRANSITION_REASON_REQUIRED"


@dataclass(frozen=True, slots=True)
class TransitionCommand:
    incident_id: uuid.UUID
    target_state: IncidentLifecycleState
    reason: str | None
    merged_into_incident_id: uuid.UUID | None
    if_match: str | None


class IncidentTransitionService:
    def __init__(
        self,
        reopen_window: timedelta,
        repository: IncidentRepository | None = None,
        activity: IncidentActivityRecorder | None = None,
        reviews: IncidentReviewService | None = None,
    ) -> None:
        self._reopen_window = reopen_window
        self._repository = repository or IncidentRepository()
        self._activity = activity or IncidentActivityRecorder()
        self._reviews = reviews or IncidentReviewService()

    async def transition(
        self, session: AsyncSession, access: WorkspaceAccess, command: TransitionCommand
    ) -> Incident:
        incident = await self._repository.lock_in_workspace(
            session, access.workspace_id, command.incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        assert_if_match(format_weak_etag(incident.id, incident.updated_at), command.if_match)

        current = _STATE(incident.lifecycle_state)
        target = command.target_state
        if current is target:
            raise IncidentAlreadyInStateError(f"The incident is already {target.value}.")
        validate_lifecycle_transition(current, target)
        if target is _STATE.CLOSED:
            # Nobody can close yet: the review owner and sign-off arrive with post-incident
            # reviews (MPS-8A.12, MPS-13.17). Say so rather than reporting a role problem.
            raise IncidentReviewRequiredError(
                "Closing requires a signed-off post-incident review, which is not available yet."
            )
        if not roles_allowed_for(current, target).intersection(access.roles):
            raise InsufficientWorkspaceRoleError(
                f"Your workspace role cannot move an incident from {current.value} to "
                f"{target.value}."
            )
        now = datetime.now(UTC)
        await self._apply_target_rules(session, access, incident, command, current, now)

        before: dict[str, object] = {"lifecycle_state": current.value}
        incident.lifecycle_state = target.value
        incident = await self._repository.save(session, incident)
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=incident.id,
                action=TRANSITIONED_ACTION,
                subject_type=INCIDENT_TARGET_TYPE,
                subject_id=incident.id,
                before=before,
                after=_after_state(incident, command.reason),
            ),
        )
        if target is _STATE.RESOLVED:
            # MPS-8A.11: resolving fires post-incident review creation.
            await self._reviews.create_on_resolution(session, access, incident)
        return incident

    async def _apply_target_rules(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident: Incident,
        command: TransitionCommand,
        current: IncidentLifecycleState,
        now: datetime,
    ) -> None:
        target = command.target_state
        is_reopen = current is _STATE.RESOLVED and target is _STATE.INVESTIGATING
        if (target in _REASON_REQUIRED_FOR or is_reopen) and not command.reason:
            raise TransitionReasonRequiredError(f"A reason is required to move to {target.value}.")
        if target is _STATE.MERGED:
            await self._validate_merge_target(session, access, incident, command)
            incident.merged_into_incident_id = command.merged_into_incident_id
        elif command.merged_into_incident_id is not None:
            raise InvalidMergeTargetError("merged_into_incident_id is only valid when merging.")

        if current is _STATE.TRIAGE and target is _STATE.INVESTIGATING:
            incident.declared_at = now
            incident.declared_by_user_id = access.user_id
        elif target is _STATE.MONITORING:
            incident.mitigated_at = now
        elif target is _STATE.RESOLVED:
            incident.resolved_at = now
        elif target is _STATE.CANCELLED:
            incident.cancelled_at = now
        elif is_reopen:
            self._ensure_within_reopen_window(incident, now)
            # Resolution history stays in the audit chain; the incident is open again.
            incident.resolved_at = None

    def _ensure_within_reopen_window(self, incident: Incident, now: datetime) -> None:
        if incident.resolved_at is None or now - incident.resolved_at > self._reopen_window:
            raise IncidentReopenWindowExpiredError(
                "This incident was resolved too long ago to reopen; declare a new incident."
            )

    async def _validate_merge_target(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident: Incident,
        command: TransitionCommand,
    ) -> None:
        target_id = command.merged_into_incident_id
        if target_id is None or target_id == incident.id:
            raise InvalidMergeTargetError("Merging needs another incident as the target.")
        target = await self._repository.find_in_workspace(session, access.workspace_id, target_id)
        if target is None or _STATE(target.lifecycle_state) not in OPEN_LIFECYCLE_STATES:
            raise InvalidMergeTargetError(
                "The merge target must be an open incident in the same workspace."
            )


def _after_state(incident: Incident, reason: str | None) -> dict[str, object]:
    after: dict[str, object] = {"lifecycle_state": incident.lifecycle_state}
    if reason:
        after["reason"] = reason
    if incident.merged_into_incident_id is not None:
        after["merged_into_incident_id"] = str(incident.merged_into_incident_id)
    return after
