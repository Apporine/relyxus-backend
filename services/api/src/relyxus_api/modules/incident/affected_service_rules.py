"""Which services an incident may name as affected (shared by declare and later edits).

A service must be in the incident's workspace and not archived; an incident names at most
MAX_AFFECTED_SERVICES services.
"""

import uuid
from collections.abc import Collection
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.catalog.model import CatalogService
from relyxus_api.modules.catalog.repository import CatalogRepository
from relyxus_api.modules.incident.affected_service_model import MAX_AFFECTED_SERVICES
from relyxus_api.shared.errors.app_errors import ValidationFailedError


class AffectedServiceInvalidError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_AFFECTED_SERVICE_INVALID"


class TooManyAffectedServicesError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_TOO_MANY_AFFECTED_SERVICES"


async def require_linkable_services(
    session: AsyncSession,
    catalog: CatalogRepository,
    workspace_id: uuid.UUID,
    service_ids: Collection[uuid.UUID],
) -> list[CatalogService]:
    if len(service_ids) > MAX_AFFECTED_SERVICES:
        raise TooManyAffectedServicesError(
            f"An incident can name at most {MAX_AFFECTED_SERVICES} affected services."
        )
    found = await catalog.find_many_in_workspace(session, workspace_id, service_ids)
    usable = {service.id: service for service in found if service.archived_at is None}
    missing = [str(service_id) for service_id in service_ids if service_id not in usable]
    if missing:
        raise AffectedServiceInvalidError(
            "Affected services must be active services of this workspace: " + ", ".join(missing)
        )
    return [usable[service_id] for service_id in service_ids]
