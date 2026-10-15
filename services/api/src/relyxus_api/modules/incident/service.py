"""Declare and read incidents (MPS-8A.07, MPS-8A.08, MPS-8A.20, MPS-8A.22).

Every state change is validated by the lifecycle rules (ADR-0004) and recorded in the
workspace audit chain inside the same transaction, so a change can never commit without
its audit entry (MPS-22A.14).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.audit.model import ActorType, AuditOutcome
from relyxus_api.modules.audit.service import AuditService, NewAuditEvent
from relyxus_api.modules.incident.lifecycle import (
    IncidentLifecycleState,
    validate_lifecycle_transition,
)
from relyxus_api.modules.incident.model import Incident, IncidentSeverity
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.shared.errors.app_errors import NotFoundError
from relyxus_api.shared.observability.correlation import get_correlation_id
from relyxus_api.shared.utils.ids import new_uuid7

INCIDENT_TARGET_TYPE = "incident"
DECLARED_ACTION = "incident.declared"
DRAFTED_ACTION = "incident.drafted"


class IncidentNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_NOT_FOUND"


@dataclass(frozen=True, slots=True)
class NewIncident:
    title: str
    severity: IncidentSeverity
    is_declared: bool


class IncidentService:
    def __init__(
        self,
        repository: IncidentRepository | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._repository = repository or IncidentRepository()
        self._audit = audit or AuditService()

    async def create(
        self, session: AsyncSession, access: WorkspaceAccess, new_incident: NewIncident
    ) -> Incident:
        """Create in triage, then declare (triage → investigating) unless saved as a draft."""
        target_state = IncidentLifecycleState.TRIAGE
        declared_at: datetime | None = None
        if new_incident.is_declared:
            target_state = IncidentLifecycleState.INVESTIGATING
            validate_lifecycle_transition(IncidentLifecycleState.TRIAGE, target_state)
            declared_at = datetime.now(UTC)

        incident = await self._repository.add(
            session,
            Incident(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                lifecycle_state=target_state.value,
                severity=new_incident.severity.value,
                title=new_incident.title,
                declared_at=declared_at,
                declared_by_user_id=access.user_id if new_incident.is_declared else None,
            ),
        )
        await self._audit.append(
            session,
            NewAuditEvent(
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                actor_type=ActorType.USER,
                actor_user_id=access.user_id,
                effective_user_id=None,
                action=DECLARED_ACTION if new_incident.is_declared else DRAFTED_ACTION,
                target_type=INCIDENT_TARGET_TYPE,
                target_id=str(incident.id),
                outcome=AuditOutcome.SUCCEEDED,
                before_state=None,
                after_state={
                    "lifecycle_state": incident.lifecycle_state,
                    "severity": incident.severity,
                    "title": incident.title,
                },
                correlation_id=get_correlation_id(),
            ),
        )
        return incident

    async def get(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> Incident:
        incident = await self._repository.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        return incident
