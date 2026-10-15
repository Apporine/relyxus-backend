"""Link incidents of one workspace (MPS-8A.31, MPS-20.31).

Rules: both incidents must be visible in the open workspace; an incident cannot link to
itself; two incidents share at most one link of each type, whichever way round it was
made. Links can be added or removed while the source incident is not closed, cancelled or
merged; the target may be in any state, because "recurrence of" usually points at a
closed incident. Both incidents are locked in ID order so concurrent opposite links
cannot both pass the duplicate check. Every change is audited once and appears on both
incidents' timelines (MPS-8A.31 "shown in timelines").

Not yet: links shown in reports (8A.31), parent/child major incidents (8A.30).
"""

import uuid
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.incident.activity import IncidentActivity, IncidentActivityRecorder
from relyxus_api.modules.incident.lifecycle import TERMINAL_LIFECYCLE_STATES, IncidentLifecycleState
from relyxus_api.modules.incident.link_model import IncidentLink, IncidentLinkType
from relyxus_api.modules.incident.link_repository import IncidentLinkRepository
from relyxus_api.modules.incident.model import Incident
from relyxus_api.modules.incident.repository import IncidentRepository
from relyxus_api.modules.incident.service import IncidentNotFoundError
from relyxus_api.modules.incident.update_service import IncidentNotEditableError
from relyxus_api.shared.errors.app_errors import ConflictError, NotFoundError, ValidationFailedError
from relyxus_api.shared.http.pagination import InvalidCursorError, Page, PageRequest, build_page
from relyxus_api.shared.utils.ids import new_uuid7

LINK_SUBJECT_TYPE = "incident_link"
LINK_ADDED_ACTION = "incident.link_added"
LINK_REMOVED_ACTION = "incident.link_removed"


class InvalidLinkTargetError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_LINK_INVALID_TARGET"


class IncidentLinkExistsError(ConflictError):
    code: ClassVar[str] = "INCIDENT_LINK_EXISTS"


class IncidentLinkNotFoundError(NotFoundError):
    code: ClassVar[str] = "INCIDENT_LINK_NOT_FOUND"


class IncidentLinkService:
    def __init__(
        self,
        links: IncidentLinkRepository | None = None,
        incidents: IncidentRepository | None = None,
        activity: IncidentActivityRecorder | None = None,
    ) -> None:
        self._links = links or IncidentLinkRepository()
        self._incidents = incidents or IncidentRepository()
        self._activity = activity or IncidentActivityRecorder()

    async def add(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        target_incident_id: uuid.UUID,
        link_type: IncidentLinkType,
    ) -> IncidentLink:
        if target_incident_id == incident_id:
            raise InvalidLinkTargetError("An incident cannot be linked to itself.")
        source, target = await self._lock_pair(session, access, incident_id, target_incident_id)
        if source is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        if target is None:
            raise InvalidLinkTargetError("The target must be an incident in this workspace.")
        _require_linkable(source)
        if await self._links.find_between(session, source.id, target.id, link_type.value):
            raise IncidentLinkExistsError(
                f"These incidents are already linked as {link_type.value}."
            )

        link = await self._links.add(
            session,
            IncidentLink(
                id=new_uuid7(),
                organization_id=access.organization_id,
                workspace_id=access.workspace_id,
                from_incident_id=source.id,
                to_incident_id=target.id,
                link_type=link_type.value,
                created_by_user_id=access.user_id,
            ),
        )
        await self._record(session, access, link, LINK_ADDED_ACTION, None, _snapshot(link))
        return link

    async def remove(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        link_id: uuid.UUID,
    ) -> None:
        source = await self._incidents.lock_in_workspace(session, access.workspace_id, incident_id)
        if source is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        _require_linkable(source)
        link = await self._links.find_for_incident(session, incident_id, link_id)
        if link is None:
            raise IncidentLinkNotFoundError("No link with this ID exists on this incident.")
        before = _snapshot(link)
        await self._links.remove(session, link.id)
        await self._record(session, access, link, LINK_REMOVED_ACTION, before, None)

    async def list(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        page_request: PageRequest,
    ) -> Page[IncidentLink]:
        incident = await self._incidents.find_in_workspace(
            session, access.workspace_id, incident_id
        )
        if incident is None:
            raise IncidentNotFoundError("No incident with this ID is visible to you.")
        fetched = await self._links.list_for_incident(
            session, incident_id, _decode_cursor(page_request), page_request.limit + 1
        )
        return build_page(fetched, page_request, lambda link: (str(link.id),))

    async def _lock_pair(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        incident_id: uuid.UUID,
        target_incident_id: uuid.UUID,
    ) -> tuple[Incident | None, Incident | None]:
        locked: dict[uuid.UUID, Incident | None] = {}
        for each_id in sorted((incident_id, target_incident_id)):
            locked[each_id] = await self._incidents.lock_in_workspace(
                session, access.workspace_id, each_id
            )
        return locked[incident_id], locked[target_incident_id]

    async def _record(
        self,
        session: AsyncSession,
        access: WorkspaceAccess,
        link: IncidentLink,
        action: str,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
    ) -> None:
        await self._activity.record(
            session,
            access,
            IncidentActivity(
                incident_id=link.from_incident_id,
                action=action,
                subject_type=LINK_SUBJECT_TYPE,
                subject_id=link.id,
                before=before,
                after=after,
                also_on_incident_ids=(link.to_incident_id,),
            ),
        )


def _require_linkable(incident: Incident) -> None:
    if IncidentLifecycleState(incident.lifecycle_state) in TERMINAL_LIFECYCLE_STATES:
        raise IncidentNotEditableError(
            f"Links of a {incident.lifecycle_state} incident can no longer be changed."
        )


def _snapshot(link: IncidentLink) -> dict[str, object]:
    return {
        "from_incident_id": str(link.from_incident_id),
        "to_incident_id": str(link.to_incident_id),
        "link_type": link.link_type,
    }


def _decode_cursor(page_request: PageRequest) -> uuid.UUID | None:
    if page_request.after is None:
        return None
    position = page_request.after
    if len(position) != 1 or not isinstance(position[0], str):
        raise InvalidCursorError("The cursor is not valid; restart from the first page.")
    try:
        return uuid.UUID(position[0])
    except ValueError as error:
        raise InvalidCursorError("The cursor is not valid; restart from the first page.") from error
