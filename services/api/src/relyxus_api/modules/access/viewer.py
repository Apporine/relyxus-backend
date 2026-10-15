"""Who is reading, attached to the database session once a workspace is opened.

Record-level visibility rules (for example restricted incidents, MPS-8A.23) need the
caller's identity in the repository layer. `open_workspace` stores it on the session;
repositories read it with `get_viewer`. A session without a viewer (system work, scripts)
must be treated as seeing only records visible to the whole workspace: fail closed.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import WorkspaceRole

_VIEWER_KEY = "relyxus.viewer"


@dataclass(frozen=True, slots=True)
class Viewer:
    user_id: uuid.UUID
    roles: frozenset[WorkspaceRole]
    team_ids: frozenset[uuid.UUID]


def set_viewer(session: AsyncSession, viewer: Viewer) -> None:
    session.info[_VIEWER_KEY] = viewer


def get_viewer(session: AsyncSession) -> Viewer | None:
    viewer = session.info.get(_VIEWER_KEY)
    return viewer if isinstance(viewer, Viewer) else None
