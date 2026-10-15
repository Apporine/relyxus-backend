"""Post-incident follow-ups (MPS-26.02, MPS-13.17, MPS-20.32 "converts to follow-up").

Follow-ups are post-incident work, so they exist once an incident is resolved: they can be
created and changed while it is resolved or closed (closed incidents still track their
follow-ups, MPS-13.17). Owners must be workspace members. Done and cancelled are final;
cancelling needs a reason. Mandatory defaults to true for SEV1 and SEV2 (register Q-37).
Every change is audited and on the timeline.

Not yet: weekly overdue reminders (MPS-13.07), Jira/ServiceNow ticket mirroring
(MPS-16.10), recurring-cause flags.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.service import WorkspaceAccess, WorkspaceAccessService
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.follow_up_model import (
    FINAL_FOLLOW_UP_STATUSES,
    FollowUpSource,
    FollowUpStatus,
    IncidentFollowUp,
)
from relyxus_api.modules.incident.follow_up_repository import IncidentFollowUpRepository
from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.model import Incident, IncidentSeverity
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.service import IncidentNotFoundError
from relyxus_api.shared.errors.app_errors import ConflictError, NotFoundError, ValidationFailedError
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.id_cursor import decode_id_cursor
from relyxus_api.shared.http.pagination import Page, PageRequest, build_page
from relyxus_api.shared.http.preconditions import assert_if_match
from relyxus_api.shared.utils.ids import new_uuid7

FOLLOW_UP_SUBJECT_TYPE = "incident_follow_up"
FOLLOW_UP_CREATED_ACTION = "incident.follow_up_created"
FOLLOW_UP_UPDATED_ACTION = "incident.follow_up_updated"
FOLLOW_UP_STATES = frozenset({IncidentLifecycleState.RESOLVED, IncidentLifecycleState.CLOSED})
MANDATORY_BY_DEFAULT = frozenset({IncidentSeverity.SEV1, IncidentSeverity.SEV2})


class FollowUpsNotAvailableError(ConflictError):
    code: ClassVar[str] = "INCIDENT_FOLLOW_UPS_NOT_AVAILABLE"


class FollowUpNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_FOLLOW_UP_NOT_FOUND"


class FollowUpNotEditableError(ConflictError):
    code: ClassVar[str] = "INCIDENT_FOLLOW_UP_NOT_EDITABLE"


class FollowUpOwnerNotMemberError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_FOLLOW_UP_OWNER_NOT_MEMBER"


class FollowUpReasonRequiredError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_FOLLOW_UP_REASON_REQUIRED"


class NoFollowUpChangesError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_FOLLOW_UP_NO_CHANGES"


@dataclass(frozen=True, slots=True)
class NewFollowUp:
    title: str
    owner_user_id: uuid.UUID | None
    due_at: datetime | None
    is_mandatory: bool | None
    source_task_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class FollowUpChanges:
    """`changed_fields` says which fields the caller sent, so null can clear owner or due."""

    changed_fields: frozenset[str]
    title: str | None = None
    owner_user_id: uuid.UUID | None = None
    due_at: datetime | None = None
    is_mandatory: bool | None = None
    status: FollowUpStatus | None = None
    reason: str | None = None
    if_match: str | None = None


class IncidentFollowUpService:
    def __init__(
        self,
        follow_ups: IncidentFollowUpRepository | None = None,
        incidents: IncidentRepository | None = None,
        activity: IncidentActivityRecorder | None = None,
        access: WorkspaceAccessService | None = None,
    ) -> None:
        self._follow_ups = follow_ups or IncidentFollowUpRepository()
        self._incidents = incidents or IncidentRepository()
        self._activity = activity or IncidentActivityRecorder()
        self._access = access or WorkspaceAccessService(AccessRepository())

    async def create(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        new_follow_up: NewFollowUp,
    ) -> IncidentFollowUp:
        incident = await self.require_post_incident(session, access, incident_id)
        return await self.add(session, access, incident, new_follow_up)

    async def add(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident: Incident,
        new_follow_up: NewFollowUp,
    ) -> IncidentFollowUp:
        """Create for an incident the caller has already checked and locked."""
        await self._require_member(session, access, new_follow_up.owner_user_id)
        is_mandatory = new_follow_up.is_mandatory
        if is_mandatory is None:
            is_mandatory = IncidentSeverity(incident.severity) in MANDATORY_BY_DEFAULT
        follow_up = await self._follow_ups.save(
            session,
            IncidentFollowUp(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                incident_id=incident.id,
                title=new_follow_up.title,
                owner_user_id=new_follow_up.owner_user_id,
                due_at=new_follow_up.due_at,
                is_mandatory=is_mandatory,
                status=FollowUpStatus.OPEN.value,
                source=(
                    FollowUpSource.MANUAL.value
                    if new_follow_up.source_task_id is None
                    else FollowUpSource.LIVE_TASK.value
                ),
                source_task_id=new_follow_up.source_task_id,
                created_by_user_id=access.user_id,
            ),
        )
        await self._record(
            session, access, follow_up, FOLLOW_UP_CREATED_ACTION, None, _snapshot(follow_up)
        )
        return follow_up

    async def list(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        page_request: PageRequest,
    ) -> Page[IncidentFollowUp]:
        incident = await self._incidents.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        fetched = await self._follow_ups.list_for_incident(
            session, incident_id, decode_id_cursor(page_request), page_request.limit + 1
        )
        return build_page(fetched, page_request, lambda follow_up: (str(follow_up.id),))

    async def update(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        follow_up_id: uuid.UUID,
        changes: FollowUpChanges,
    ) -> IncidentFollowUp:
        await self.require_post_incident(session, access, incident_id)
        follow_up = await self._follow_ups.lock(session, incident_id, follow_up_id)
        if follow_up is None:
            raise FollowUpNotFoundError("No follow-up with this ID exists on this incident.")
        assert_if_match(format_weak_etag(follow_up.id, follow_up.updated_at), changes.if_match)
        if FollowUpStatus(follow_up.status) in FINAL_FOLLOW_UP_STATUSES:
            raise FollowUpNotEditableError(f"A {follow_up.status} follow-up can no longer change.")
        if "owner_user_id" in changes.changed_fields:
            await self._require_member(session, access, changes.owner_user_id)

        before = _snapshot(follow_up)
        _apply(follow_up, changes, access.user_id)
        after = _snapshot(follow_up)
        changed = sorted(key for key in after if after[key] != before[key])
        if not changed:
            raise NoFollowUpChangesError("The request does not change the follow-up.")
        follow_up = await self._follow_ups.save(session, follow_up)
        await self._record(
            session,
            access,
            follow_up,
            FOLLOW_UP_UPDATED_ACTION,
            {key: before[key] for key in changed},
            {key: after[key] for key in changed},
        )
        return follow_up

    async def require_post_incident(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> Incident:
        """Lock the incident and require it to be resolved or closed."""
        incident = await self._incidents.lock_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        if IncidentLifecycleState(incident.lifecycle_state) not in FOLLOW_UP_STATES:
            raise FollowUpsNotAvailableError(
                "Follow-ups are post-incident work; they are available once the incident is "
                f"resolved, and this one is {incident.lifecycle_state}."
            )
        return incident

    async def _require_member(
        self, session: AsyncSession, access: WorkspaceAccess, user_id: uuid.UUID | None
    ) -> None:
        if user_id is not None and not await self._access.is_workspace_member(
            session, user_id, access.workspace_id
        ):
            raise FollowUpOwnerNotMemberError(
                "The follow-up owner must be a member of this workspace."
            )

    async def _record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        follow_up: IncidentFollowUp,
        action: str,
        before: dict[str, object] | None,
        after: dict[str, object],
    ) -> None:
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=follow_up.incident_id,
                action=action,
                subject_type=FOLLOW_UP_SUBJECT_TYPE,
                subject_id=follow_up.id,
                before=before,
                after=after,
            ),
        )


def _apply(follow_up: IncidentFollowUp, changes: FollowUpChanges, actor_id: uuid.UUID) -> None:
    fields = changes.changed_fields
    if "title" in fields and changes.title is not None:
        follow_up.title = changes.title
    if "owner_user_id" in fields:
        follow_up.owner_user_id = changes.owner_user_id
    if "due_at" in fields:
        follow_up.due_at = changes.due_at
    if "is_mandatory" in fields and changes.is_mandatory is not None:
        follow_up.is_mandatory = changes.is_mandatory
    if changes.status is None or changes.status.value == follow_up.status:
        return
    if changes.status is FollowUpStatus.CANCELLED:
        if not changes.reason:
            raise FollowUpReasonRequiredError("A reason is required to cancel a follow-up.")
        follow_up.cancellation_reason = changes.reason
    if changes.status is FollowUpStatus.DONE:
        follow_up.completed_at = datetime.now(UTC)
        follow_up.completed_by_user_id = actor_id
    follow_up.status = changes.status.value


def _snapshot(follow_up: IncidentFollowUp) -> dict[str, object]:
    """Audit-safe view: strings, booleans and nulls only."""
    return {
        "title": follow_up.title,
        "status": follow_up.status,
        "is_mandatory": follow_up.is_mandatory,
        "owner_user_id": None if follow_up.owner_user_id is None else str(follow_up.owner_user_id),
        "due_at": None
        if follow_up.due_at is None
        else follow_up.due_at.astimezone(UTC).isoformat(),
        "source_task_id": (
            None if follow_up.source_task_id is None else str(follow_up.source_task_id)
        ),
        "cancellation_reason": follow_up.cancellation_reason,
    }
