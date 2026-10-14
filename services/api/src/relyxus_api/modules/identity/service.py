"""Map verified tokens to provisioned users (MPS-14.10)."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import UserStatus
from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal


@dataclass(frozen=True, slots=True)
class ResolvedIdentity:
    issuer: str
    subject: str
    email: str | None
    display_name: str | None
    authenticated_at: datetime | None
    is_provisioned: bool
    user_id: uuid.UUID | None
    status: UserStatus | None


class IdentityService:
    def __init__(self, repository: AccessRepository | None = None) -> None:
        self._repository = repository or AccessRepository()

    async def resolve(
        self, session: AsyncSession, principal: AuthenticatedPrincipal
    ) -> ResolvedIdentity:
        user = await self._repository.find_user_by_identity(
            session, principal.issuer, principal.subject
        )
        if user is None:
            return ResolvedIdentity(
                issuer=principal.issuer,
                subject=principal.subject,
                email=principal.email,
                display_name=principal.display_name,
                authenticated_at=principal.authenticated_at,
                is_provisioned=False,
                user_id=None,
                status=None,
            )
        email = user.email if user.email is not None else principal.email
        display_name = user.display_name
        if display_name is None:
            display_name = principal.display_name
        return ResolvedIdentity(
            issuer=principal.issuer,
            subject=principal.subject,
            email=email,
            display_name=display_name,
            authenticated_at=principal.authenticated_at,
            is_provisioned=True,
            user_id=user.id,
            status=UserStatus(user.status),
        )
