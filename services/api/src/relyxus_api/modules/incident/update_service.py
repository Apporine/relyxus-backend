"""Edit an open incident's title, severity or reported times (MPS-8.06, MPS-8A.20, MPS-22A.05).

A severity change is a human override of the suggested severity, so it needs a reason
(MPS-8.06). Impact-started and detected times can be corrected as facts emerge; they
must stay plausible (see `reported_times`). The incident row is locked, an optional
If-Match is honoured, and the change is audited in the same transaction with only the
fields that changed.

Not yet: raising severity to SEV1 should open the war room, prompt regulator
classification and run the type's SEV1 automations (MPS-8A.19); those features do not
exist yet.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.lifecycle import TERMINAL_LIFECYCLE_STATES, IncidentLifecycleState
from relyxus_api.modules.incident.model import Incident, IncidentSeverity
from relyxus_api.modules.incident.reported_times import (
    isoformat_or_none,
    validate_reported_times,
)
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.service import INCIDENT_TARGET_TYPE, IncidentNotFoundError
from relyxus_api.shared.errors.app_errors import ConflictError, ValidationFailedError
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.preconditions import assert_if_match

UPDATED_ACTION = "incident.updated"


class IncidentNotEditableError(ConflictError):
    code: ClassVar[str] = "INCIDENT_NOT_EDITABLE"


class SeverityChangeReasonRequiredError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_SEVERITY_REASON_REQUIRED"


class NoIncidentChangesError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_NO_CHANGES"


@dataclass(frozen=True, slots=True)
class IncidentChanges:
    incident_id: uuid.UUID
    title: str | None
    severity: IncidentSeverity | None
    reason: str | None
    if_match: str | None
    impact_started_at: datetime | None = None
    detected_at: datetime | None = None


class IncidentUpdateService:
    def __init__(
        self,
        repository: IncidentRepository | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._repository = repository or IncidentRepository()
        self._activity = activity or IncidentActivityRecorder()

    async def update(
        self, session: AsyncSession, access: WorkspaceAccess, changes: IncidentChanges
    ) -> Incident:
        incident = await self._repository.lock_in_workspace(
            session, access.workspace_id, changes.incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        assert_if_match(format_weak_etag(incident.id, incident.updated_at), changes.if_match)
        if IncidentLifecycleState(incident.lifecycle_state) in TERMINAL_LIFECYCLE_STATES:
            raise IncidentNotEditableError(
                f"A {incident.lifecycle_state} incident can no longer be changed."
            )

        before: dict[str, object] = {}
        after: dict[str, object] = {}
        if changes.title is not None and changes.title != incident.title:
            before["title"], after["title"] = incident.title, changes.title
            incident.title = changes.title
        if changes.severity is not None and changes.severity.value != incident.severity:
            if not changes.reason:
                raise SeverityChangeReasonRequiredError("A reason is required to change severity.")
            before["severity"], after["severity"] = incident.severity, changes.severity.value
            incident.severity = changes.severity.value
        self._apply_reported_times(incident, changes, before, after)
        if not after:
            raise NoIncidentChangesError("The request does not change the incident.")
        if changes.reason:
            after["reason"] = changes.reason

        incident = await self._repository.save(session, incident)
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=incident.id,
                action=UPDATED_ACTION,
                subject_type=INCIDENT_TARGET_TYPE,
                subject_id=incident.id,
                before=before,
                after=after,
            ),
        )
        return incident

    @staticmethod
    def _apply_reported_times(
        incident: Incident,
        changes: IncidentChanges,
        before: dict[str, object],
        after: dict[str, object],
    ) -> None:
        impact_started_at = changes.impact_started_at or incident.impact_started_at
        detected_at = changes.detected_at or incident.detected_at
        if (impact_started_at, detected_at) == (incident.impact_started_at, incident.detected_at):
            return
        validate_reported_times(impact_started_at, detected_at, datetime.now(UTC))
        for name, current, new in (
            ("impact_started_at", incident.impact_started_at, impact_started_at),
            ("detected_at", incident.detected_at, detected_at),
        ):
            if new != current:
                before[name], after[name] = isoformat_or_none(current), isoformat_or_none(new)
        incident.impact_started_at = impact_started_at
        incident.detected_at = detected_at
