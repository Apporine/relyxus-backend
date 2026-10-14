"""Turns a verified identity plus a requested workspace into a tenant scope (MP-10.01).

The workspace ID comes from the client, so it is only a request: access exists only if the
database holds an active user with a grant in that workspace. Unknown and forbidden
workspaces fail identically, so callers cannot probe which workspace IDs exist.
"""

import uuid
from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import UserStatus, WorkspaceRole
from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from relyxus_api.shared.errors.app_errors import PermissionDeniedError


class UserNotProvisionedError(PermissionDeniedError):
    code: ClassVar[str] = "USER_NOT_PROVISIONED"


class UserNotActiveError(PermissionDeniedError):
    code: ClassVar[str] = "USER_NOT_ACTIVE"


class WorkspaceAccessDeniedError(PermissionDeniedError):
    code: ClassVar[str] = "WORKSPACE_ACCESS_DENIED"


@dataclass(frozen=True, slots=True)
class WorkspaceAccess:
    user_id: uuid.UUID
    organization_id: uuid.UUID
    workspace_id: uuid.UUID
    roles: frozenset[WorkspaceRole]


class WorkspaceAccessService:
    def __init__(self, repository: AccessRepository) -> None:
        self._repository = repository

    async def open_workspace(
        self, session: AsyncSession, principal: AuthenticatedPrincipal, workspace_id: uuid.UUID
    ) -> WorkspaceAccess:
        """Resolve access and apply the tenant context. Must run inside a transaction."""
        user = await self._repository.find_user_by_identity(
            session, principal.issuer, principal.subject
        )
        if user is None:
            raise UserNotProvisionedError("Your account has not been provisioned in Relyxus.")
        if user.status != UserStatus.ACTIVE:
            raise UserNotActiveError("Your Relyxus account is not active.")

        grants = await self._repository.list_workspace_grants(session, user.id, workspace_id)
        if not grants:
            raise WorkspaceAccessDeniedError("You do not have access to this workspace.")

        access = WorkspaceAccess(
            user_id=user.id,
            organization_id=grants[0].organization_id,
            workspace_id=workspace_id,
            roles=frozenset(WorkspaceRole(grant.role) for grant in grants),
        )
        await apply_tenant_context(
            session,
            TenantContext(organization_id=access.organization_id, workspace_id=workspace_id),
        )
        return access
