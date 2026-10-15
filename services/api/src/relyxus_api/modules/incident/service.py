"""Declare and read incidents (MPS-8A.07, MPS-8A.08, MPS-8A.20, MPS-8A.22).

Every state change is validated by the lifecycle rules (ADR-0004) and recorded in the
workspace audit chain and the incident timeline inside the same transaction, so a change
can never commit without its audit entry (MPS-22A.14).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.catalog.repository import CatalogRepository
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.affected_service_model import IncidentAffectedService
from relyxus_api.modules.incident.affected_service_repository import AffectedServiceRepository
from relyxus_api.modules.incident.affected_service_rules import require_linkable_services
from relyxus_api.modules.incident.lifecycle import (
    IncidentLifecycleState,
    validate_lifecycle_transition,
)
from relyxus_api.modules.incident.model import Incident, IncidentSeverity, IncidentVisibility
from relyxus_api.modules.incident.reported_times import (
    isoformat_or_none,
    validate_reported_times,
)
from relyxus_api.modules.incident.repository import IncidentListQuery, IncidentRepository
from relyxus_api.modules.incident.type_repository import IncidentTypeRepository
from relyxus_api.modules.incident.type_rules import resolve_declaration
from relyxus_api.shared.errors.app_errors import NotFoundError
from relyxus_api.shared.http.pagination import InvalidCursorError, Page, PageRequest, build_page
from relyxus_api.shared.utils.ids import new_uuid7

INCIDENT_TARGET_TYPE = "incident"
DECLARED_ACTION = "incident.declared"
DRAFTED_ACTION = "incident.drafted"


class IncidentNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_NOT_FOUND"


@dataclass(frozen=True, slots=True)
class IncidentFilters:
    """Empty sets mean "any"."""

    lifecycle_states: frozenset[IncidentLifecycleState] = frozenset()
    severities: frozenset[IncidentSeverity] = frozenset()
    service_ids: frozenset[uuid.UUID] = frozenset()
    incident_type_ids: frozenset[uuid.UUID] = frozenset()


@dataclass(frozen=True, slots=True)
class NewIncident:
    """`None` severity or visibility means "not given": the type's default applies."""

    title: str
    severity: IncidentSeverity | None
    is_declared: bool
    impact_started_at: datetime | None = None
    # Defaults to the moment the incident is reported in Relyxus.
    detected_at: datetime | None = None
    affected_service_ids: tuple[uuid.UUID, ...] = ()
    visibility: IncidentVisibility | None = None
    incident_type_id: uuid.UUID | None = None


class IncidentService:
    def __init__(
        self,
        repository: IncidentRepository | None = None,
        activity: IncidentActivityRecorder | None = None,
        catalog: CatalogRepository | None = None,
        affected_services: AffectedServiceRepository | None = None,
    ) -> None:
        self._repository = repository or IncidentRepository()
        self._activity = activity or IncidentActivityRecorder()
        self._catalog = catalog or CatalogRepository()
        self._affected_services = affected_services or AffectedServiceRepository()
        self._types = IncidentTypeRepository()

    async def create(
        self, session: AsyncSession, access: WorkspaceAccess, new_incident: NewIncident
    ) -> Incident:
        """Create in triage, then declare (triage → investigating) unless saved as a draft."""
        now = datetime.now(UTC)
        detected_at = new_incident.detected_at or now
        validate_reported_times(new_incident.impact_started_at, detected_at, now)
        service_ids = tuple(dict.fromkeys(new_incident.affected_service_ids))
        await require_linkable_services(session, self._catalog, access.workspace_id, service_ids)
        declaration = await resolve_declaration(
            session,
            self._types,
            access.workspace_id,
            new_incident.incident_type_id,
            new_incident.severity,
            new_incident.visibility,
        )
        target_state = IncidentLifecycleState.TRIAGE
        declared_at: datetime | None = None
        if new_incident.is_declared:
            target_state = IncidentLifecycleState.INVESTIGATING
            validate_lifecycle_transition(IncidentLifecycleState.TRIAGE, target_state)
            declared_at = now

        number = await self._repository.allocate_number(session, access.workspace_id)
        incident = await self._repository.add(
            session,
            Incident(
                id=new_uuid7(),
                number=number,
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                lifecycle_state=target_state.value,
                severity=declaration.severity.value,
                incident_type_id=declaration.type_id,
                incident_type_version=declaration.type_version,
                title=new_incident.title,
                declared_at=declared_at,
                declared_by_user_id=access.user_id if new_incident.is_declared else None,
                impact_started_at=new_incident.impact_started_at,
                visibility=declaration.visibility.value,
                created_by_user_id=access.user_id,
                detected_at=detected_at,
            ),
        )
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=incident.id,
                action=DECLARED_ACTION if new_incident.is_declared else DRAFTED_ACTION,
                subject_type=INCIDENT_TARGET_TYPE,
                subject_id=incident.id,
                before=None,
                after={
                    "lifecycle_state": incident.lifecycle_state,
                    "severity": incident.severity,
                    "title": incident.title,
                    "impact_started_at": isoformat_or_none(incident.impact_started_at),
                    "detected_at": isoformat_or_none(incident.detected_at),
                    **_service_ids_state(service_ids),
                    **_visibility_state(declaration.visibility),
                    **_type_state(declaration.type_id, declaration.type_version),
                },
            ),
        )
        for service_id in service_ids:
            await self._affected_services.add(
                session,
                IncidentAffectedService(
                    id=new_uuid7(),
                    organization_id=access.organization_id,
                    workspace_id=access.workspace_id,
                    incident_id=incident.id,
                    service_id=service_id,
                    added_by_user_id=access.user_id,
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

    async def list(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        filters: IncidentFilters,
        page_request: PageRequest,
    ) -> Page[Incident]:
        """Incidents of the open workspace, newest first (MPS-15.02 incident list)."""
        fetched = await self._repository.list_in_workspace(
            session,
            access.workspace_id,
            IncidentListQuery(
                lifecycle_states={state.value for state in filters.lifecycle_states},
                severities={severity.value for severity in filters.severities},
                service_ids=filters.service_ids,
                incident_type_ids=filters.incident_type_ids,
            ),
            before_id=_decode_incident_cursor(page_request),
            limit=page_request.limit + 1,
        )
        return build_page(fetched, page_request, lambda incident: (str(incident.id),))


def _service_ids_state(service_ids: tuple[uuid.UUID, ...]) -> dict[str, object]:
    """Only present when services were named, so earlier audit shapes stay unchanged."""
    if not service_ids:
        return {}
    return {"affected_service_ids": [str(service_id) for service_id in service_ids]}


def _type_state(type_id: uuid.UUID | None, type_version: int | None) -> dict[str, object]:
    """Only present when declared under a type, so earlier audit shapes stay unchanged."""
    if type_id is None:
        return {}
    return {"incident_type_id": str(type_id), "incident_type_version": type_version}


def _visibility_state(visibility: IncidentVisibility) -> dict[str, object]:
    """Only present when not workspace-wide, so earlier audit shapes stay unchanged."""
    if visibility is IncidentVisibility.WORKSPACE:
        return {}
    return {"visibility": visibility.value}


def _decode_incident_cursor(page_request: PageRequest) -> uuid.UUID | None:
    if page_request.after is None:
        return None
    position = page_request.after
    if len(position) != 1 or not isinstance(position[0], str):
        raise InvalidCursorError("The cursor is not valid; restart from the first page.")
    try:
        return uuid.UUID(position[0])
    except ValueError as error:
        raise InvalidCursorError("The cursor is not valid; restart from the first page.") from error
