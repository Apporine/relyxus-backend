"""Edit an open incident's title or severity (MPS-8.06, MPS-22A.05, MPS-8A.22).

A severity change is a human override of the suggested severity, so it needs a reason
(MPS-8.06). The incident row is locked, an optional If-Match is honoured, and the change is
audited in the same transaction with only the fields that changed.

Not yet: raising severity to SEV1 should open the war room, prompt regulator
classification and run the type's SEV1 automations (MPS-8A.19); those features do not
exist yet.
"""

import uuid
from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.audit.model import ActorType, AuditOutcome
from relyxus_api.modules.audit.service import AuditService, NewAuditEvent
from relyxus_api.modules.incident.lifecycle import TERMINAL_LIFECYCLE_STATES, IncidentLifecycleState
from relyxus_api.modules.incident.model import Incident, IncidentSeverity
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.service import INCIDENT_TARGET_TYPE, IncidentNotFoundError
from relyxus_api.shared.errors.app_errors import ConflictError, ValidationFailedError
from relyxus_api.shared.http.etag import format_weak_etag
from relyxus_api.shared.http.preconditions import assert_if_match
from relyxus_api.shared.observability.correlation import get_correlation_id

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


class IncidentUpdateService:
    def __init__(
        self, repository: IncidentRepository | None = None, audit: AuditService | None = None
    ) -> None:
        self._repository = repository or IncidentRepository()
        self._audit = audit or AuditService()

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
        if not after:
            raise NoIncidentChangesError("The request does not change the incident.")
        if changes.reason:
            after["reason"] = changes.reason

        incident = await self._repository.save(session, incident)
        await self._audit.append(
            session,
            NewAuditEvent(
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                actor_type=ActorType.USER,
                actor_user_id=access.user_id,
                effective_user_id=None,
                action=UPDATED_ACTION,
                target_type=INCIDENT_TARGET_TYPE,
                target_id=str(incident.id),
                outcome=AuditOutcome.SUCCEEDED,
                before_state=before,
                after_state=after,
                correlation_id=get_correlation_id(),
            ),
        )
        return incident
