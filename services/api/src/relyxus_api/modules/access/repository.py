"""Queries for identities, role grants and the workspaces they open. No access rules here
(context.md §1): row-level security decides visibility, the service decides access."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Row, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import User, WorkspaceMembership
from relyxus_api.modules.team.model import TeamMember, TeamRoleGrant
from relyxus_api.modules.tenancy.model import Organization, Workspace
from relyxus_api.shared.db.transaction_settings import set_transaction_settings

IDP_ISSUER_SETTING = "app.idp_issuer"
IDP_SUBJECT_SETTING = "app.idp_subject"
USER_SETTING = "app.user_id"


type _ListingRow = tuple[uuid.UUID, str, str, str, uuid.UUID, str, Sequence[str]]


@dataclass(frozen=True, slots=True)
class WorkspaceListing:
    workspace_id: uuid.UUID
    workspace_key: str
    workspace_name: str
    data_residency_region: str
    organization_id: uuid.UUID
    organization_name: str
    roles: tuple[str, ...]


class AccessRepository:
    async def find_user_by_identity(
        self, session: AsyncSession, issuer: str, subject: str
    ) -> User | None:
        # RLS only reveals the user row matching this identity context.
        await set_transaction_settings(
            session, {IDP_ISSUER_SETTING: issuer, IDP_SUBJECT_SETTING: subject}
        )
        user: User | None = await session.scalar(
            select(User).where(User.idp_issuer == issuer, User.idp_subject == subject)
        )
        return user

    async def apply_user_context(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        """Lets RLS reveal this user's own grants and the workspaces they belong to."""
        await set_transaction_settings(session, {USER_SETTING: str(user_id)})

    async def clear_user_context(self, session: AsyncSession) -> None:
        """Drop user-based visibility so only the tenant context governs what RLS reveals."""
        await set_transaction_settings(session, {USER_SETTING: ""})

    async def list_workspace_grants(
        self, session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> list[WorkspaceMembership]:
        memberships = await session.scalars(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        return list(memberships)

    async def list_team_roles(
        self, session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> set[str]:
        """Roles the user inherits from their teams in this workspace (Q-18). Needs the user
        context: RLS reveals the user's own team memberships and those teams' grants."""
        roles = await session.scalars(
            select(TeamRoleGrant.role)
            .join(TeamMember, TeamMember.team_id == TeamRoleGrant.team_id)
            .where(TeamMember.user_id == user_id, TeamRoleGrant.workspace_id == workspace_id)
        )
        return set(roles)

    async def list_team_ids(
        self, session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> set[uuid.UUID]:
        """Teams the user belongs to in this workspace. Needs the user context."""
        team_ids = await session.scalars(
            select(TeamMember.team_id).where(
                TeamMember.user_id == user_id, TeamMember.workspace_id == workspace_id
            )
        )
        return set(team_ids)

    async def list_workspaces_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        after_workspace_id: uuid.UUID | None,
        limit: int,
    ) -> Sequence[WorkspaceListing]:
        """Keyset page ordered by workspace ID, one row per workspace with its roles."""
        query = self._workspace_listing_query().where(WorkspaceMembership.user_id == user_id)
        if after_workspace_id is not None:
            query = query.where(Workspace.id > after_workspace_id)
        rows = await session.execute(query.order_by(Workspace.id).limit(limit))
        return [self._to_listing(row) for row in rows]

    async def find_workspace_listing(
        self, session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> WorkspaceListing | None:
        rows = await session.execute(
            self._workspace_listing_query().where(
                WorkspaceMembership.user_id == user_id, Workspace.id == workspace_id
            )
        )
        row = rows.first()
        return None if row is None else self._to_listing(row)

    @staticmethod
    def _workspace_listing_query() -> Select[_ListingRow]:
        return (
            select(
                Workspace.id,
                Workspace.key,
                Workspace.name,
                Workspace.data_residency_region,
                Organization.id,
                Organization.name,
                func.array_agg(WorkspaceMembership.role.distinct()),
            )
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .join(Organization, Organization.id == Workspace.organization_id)
            .group_by(Workspace.id, Organization.id)
        )

    @staticmethod
    def _to_listing(row: Row[_ListingRow]) -> WorkspaceListing:
        workspace_id, key, name, region, organization_id, organization_name, roles = row._tuple()
        return WorkspaceListing(
            workspace_id=workspace_id,
            workspace_key=key,
            workspace_name=name,
            data_residency_region=region,
            organization_id=organization_id,
            organization_name=organization_name,
            roles=tuple(sorted(roles)),
        )
