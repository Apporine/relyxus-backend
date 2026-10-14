"""Request-scoped unit of work for workspace endpoints.

Opens one transaction, resolves the caller's workspace access and applies the tenant
context before the endpoint runs. It uses `scope="function"` so the commit (or rollback)
finishes before the response is sent: a failed commit can never follow a success response
(MP-34.01).
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.service import WorkspaceAccess, WorkspaceAccessService
from relyxus_api.shared.auth.dependencies import AuthenticatedPrincipalDependency
from relyxus_api.shared.constants import WORKSPACE_HEADER


@dataclass(frozen=True, slots=True)
class WorkspaceSession:
    session: AsyncSession
    access: WorkspaceAccess


async def open_workspace_session(
    request: Request,
    principal: AuthenticatedPrincipalDependency,
    workspace_id: Annotated[uuid.UUID, Header(alias=WORKSPACE_HEADER)],
) -> AsyncIterator[WorkspaceSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    service = WorkspaceAccessService(AccessRepository())
    async with session_factory() as session, session.begin():
        access = await service.open_workspace(session, principal, workspace_id)
        yield WorkspaceSession(session=session, access=access)


WorkspaceSessionDependency = Annotated[
    WorkspaceSession, Depends(open_workspace_session, scope="function")
]
