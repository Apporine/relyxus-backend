from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relyxus_api.modules.identity.service import IdentityService, ResolvedIdentity
from relyxus_api.shared.auth.dependencies import AuthenticatedPrincipalDependency


async def open_identity_session(
    request: Request,
    principal: AuthenticatedPrincipalDependency,
) -> AsyncIterator[ResolvedIdentity]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        yield await IdentityService().resolve(session, principal)


ResolvedIdentityDependency = Annotated[ResolvedIdentity, Depends(open_identity_session)]
