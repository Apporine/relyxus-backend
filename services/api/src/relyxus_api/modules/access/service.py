"""Turns a verified identity into a user and, on request, a workspace scope (MP-10.01).

A workspace ID from the client is only a request: access exists only if the database holds
an active user with a grant in that workspace. Unknown and forbidden workspaces fail
identically, so callers cannot probe which workspace IDs exist.
"""

import uuid
from dataclasses import dataclass, replace
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import User, UserStatus, WorkspaceRole
from relyxus_api.modules.access.repository import AccessRepository, WorkspaceListing
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from relyxus_api.shared.errors.app_errors import PermissionDeniedError
from relyxus_api.shared.http.pagination import Page, PageRequest, build_page


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

    async def resolve_active_user(
        self, session: AsyncSession, principal: AuthenticatedPrincipal
    ) -> User:
        """Map the verified identity to an active user and scope RLS to that user."""
        user = await self._repository.find_user_by_identity(
            session, principal.issuer, principal.subject
        )
        if user is None:
            raise UserNotProvisionedError("Your account has not been provisioned in Relyxus.")
        if user.status != UserStatus.ACTIVE:
            raise UserNotActiveError("Your Relyxus account is not active.")
        await self._repository.apply_user_context(session, user.id)
        return user

    async def open_workspace(
        self, session: AsyncSession, principal: AuthenticatedPrincipal, workspace_id: uuid.UUID
    ) -> WorkspaceAccess:
        """Resolve access and apply the tenant context. Must run inside a transaction."""
        user = await self.resolve_active_user(session, principal)
        grants = await self._repository.list_workspace_grants(session, user.id, workspace_id)
        if not grants:
            raise WorkspaceAccessDeniedError("You do not have access to this workspace.")

        # Q-18: direct grants plus the user's teams' grants. Team roles only reach people who
        # are direct members, so removing a membership removes every role in the workspace.
        team_roles = await self._repository.list_team_roles(session, user.id, workspace_id)
        access = WorkspaceAccess(
            user_id=user.id,
            organization_id=grants[0].organization_id,
            workspace_id=workspace_id,
            roles=frozenset(WorkspaceRole(role) for role in {g.role for g in grants} | team_roles),
        )
        await apply_tenant_context(
            session,
            TenantContext(organization_id=access.organization_id, workspace_id=workspace_id),
        )
        # From here on, only the chosen tenant is visible, never the caller's other
        # organisations (the user context would widen workspace and org reads).
        await self._repository.clear_user_context(session)
        return access

    async def is_workspace_member(
        self, session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> bool:
        """Whether the user holds any role in the workspace. Needs the tenant context."""
        grants = await self._repository.list_workspace_grants(session, user_id, workspace_id)
        return bool(grants)

    async def list_my_workspaces(
        self, session: AsyncSession, principal: AuthenticatedPrincipal, page_request: PageRequest
    ) -> Page[WorkspaceListing]:
        """Every workspace the caller holds a role in, across organisations (MPS-15.02)."""
        async with session.begin():
            user = await self.resolve_active_user(session, principal)
            after = uuid.UUID(str(page_request.after[0])) if page_request.after else None
            fetched = await self._repository.list_workspaces_for_user(
                session, user.id, after, page_request.limit + 1
            )
        return build_page(fetched, page_request, lambda listing: (str(listing.workspace_id),))

    async def describe_workspace(
        self, session: AsyncSession, access: WorkspaceAccess
    ) -> WorkspaceListing:
        listing = await self._repository.find_workspace_listing(
            session, access.user_id, access.workspace_id
        )
        if listing is None:
            # Access was just resolved in this transaction, so this means a concurrent
            # revocation; deny rather than report a workspace the caller can no longer use.
            raise WorkspaceAccessDeniedError("You do not have access to this workspace.")
        # Report the effective roles, team grants included (Q-18).
        return replace(listing, roles=tuple(sorted(role.value for role in access.roles)))
