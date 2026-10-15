"""Name the services an incident affects (MPS-8A.08, MPS-20.12).

Services can be named at declaration or added and removed later while the incident is
not closed, cancelled or merged. Only active services of the incident's workspace can be
added (see `affected_service_rules`). Every change is audited and on the timeline.
"""

import uuid
from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.catalog.model import CatalogService
from relyxus_api.modules.catalog.repository import CatalogRepository
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.affected_service_model import (
    MAX_AFFECTED_SERVICES,
    IncidentAffectedService,
)
from relyxus_api.modules.incident.affected_service_repository import AffectedServiceRepository
from relyxus_api.modules.incident.affected_service_rules import (
    TooManyAffectedServicesError,
    require_linkable_services,
)
from relyxus_api.modules.incident.lifecycle import TERMINAL_LIFECYCLE_STATES, IncidentLifecycleState
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.service import INCIDENT_TARGET_TYPE, IncidentNotFoundError
from relyxus_api.modules.incident.update_service import IncidentNotEditableError
from relyxus_api.shared.errors.app_errors import NotFoundError
from relyxus_api.shared.utils.ids import new_uuid7

SERVICE_ADDED_ACTION = "incident.service_added"
SERVICE_REMOVED_ACTION = "incident.service_removed"


class AffectedServiceNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_AFFECTED_SERVICE_NOT_FOUND"


@dataclass(frozen=True, slots=True)
class AffectedService:
    link: IncidentAffectedService
    service: CatalogService


class AffectedServicesService:
    def __init__(
        self,
        links: AffectedServiceRepository | None = None,
        incidents: IncidentRepository | None = None,
        catalog: CatalogRepository | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._links = links or AffectedServiceRepository()
        self._incidents = incidents or IncidentRepository()
        self._catalog = catalog or CatalogRepository()
        self._activity = activity or IncidentActivityRecorder()

    async def list(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> list[AffectedService]:
        incident = await self._incidents.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        links = await self._links.list_for_incident(session, incident_id)
        services = await self._catalog.find_many_in_workspace(
            session, access.workspace_id, [link.service_id for link in links]
        )
        by_id = {service.id: service for service in services}
        return [AffectedService(link=link, service=by_id[link.service_id]) for link in links]

    async def add(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        service_id: uuid.UUID,
    ) -> AffectedService:
        """Idempotent: naming a service already listed returns the existing entry."""
        await self._lock_open_incident(session, access, incident_id)
        (service,) = await require_linkable_services(
            session, self._catalog, access.workspace_id, [service_id]
        )
        existing = await self._links.find(session, incident_id, service_id)
        if existing is not None:
            return AffectedService(link=existing, service=service)
        if await self._links.count_for_incident(session, incident_id) >= MAX_AFFECTED_SERVICES:
            raise TooManyAffectedServicesError(
                f"An incident can name at most {MAX_AFFECTED_SERVICES} affected services."
            )
        link = await self._links.add(
            session,
            IncidentAffectedService(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                incident_id=incident_id,
                service_id=service_id,
                added_by_user_id=access.user_id,
            ),
        )
        await self._record(
            session,
            access,
            incident_id,
            SERVICE_ADDED_ACTION,
            None,
            {"service_id": str(service_id)},
        )
        return AffectedService(link=link, service=service)

    async def remove(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        service_id: uuid.UUID,
    ) -> None:
        await self._lock_open_incident(session, access, incident_id)
        link = await self._links.find(session, incident_id, service_id)
        if link is None:
            raise AffectedServiceNotFoundError("This service is not listed on the incident.")
        await self._links.remove(session, link.id)
        await self._record(
            session,
            access,
            incident_id,
            SERVICE_REMOVED_ACTION,
            {"service_id": str(service_id)},
            None,
        )

    async def _lock_open_incident(
        self, session: AsyncSession, access: WorkspaceAccess, incident_id: uuid.UUID
    ) -> None:
        incident = await self._incidents.lock_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        if IncidentLifecycleState(incident.lifecycle_state) in TERMINAL_LIFECYCLE_STATES:
            raise IncidentNotEditableError(
                f"Affected services of a {incident.lifecycle_state} incident can no longer change."
            )

    async def _record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        action: str,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
    ) -> None:
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=incident_id,
                action=action,
                subject_type=INCIDENT_TARGET_TYPE,
                subject_id=incident_id,
                before=before,
                after=after,
            ),
        )
