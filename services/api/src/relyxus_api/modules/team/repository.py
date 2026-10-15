"""Team persistence. Queries only; rules live in the team service."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.team.model import Team, TeamMember, TeamRoleGrant


class TeamRepository:
    async def save_team(self, session: AsyncSession, team: Team) -> Team:
        session.add(team)
        await session.flush()
        await session.refresh(team)
        return team

    async def find_by_key(
        self, session: AsyncSession, workspace_id: uuid.UUID, key: str
    ) -> Team | None:
        team: Team | None = await session.scalar(
            select(Team).where(Team.workspace_id == workspace_id, Team.key == key)
        )
        return team

    async def find_in_workspace(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        team_id: uuid.UUID,
        *,
        is_locking: bool = False,
    ) -> Team | None:
        query = select(Team).where(Team.id == team_id, Team.workspace_id == workspace_id)
        if is_locking:
            query = query.with_for_update()
        team: Team | None = await session.scalar(query)
        return team

    async def list_in_workspace(
        self, session: AsyncSession, workspace_id: uuid.UUID, after_id: uuid.UUID | None, limit: int
    ) -> list[Team]:
        """Oldest first (UUIDv7 order), keyset page after `after_id`."""
        query = select(Team).where(Team.workspace_id == workspace_id)
        if after_id is not None:
            query = query.where(Team.id > after_id)
        teams = await session.scalars(query.order_by(Team.id).limit(limit))
        return list(teams)

    async def save_member(self, session: AsyncSession, member: TeamMember) -> TeamMember:
        session.add(member)
        await session.flush()
        await session.refresh(member)
        return member

    async def find_member(
        self, session: AsyncSession, team_id: uuid.UUID, user_id: uuid.UUID
    ) -> TeamMember | None:
        member: TeamMember | None = await session.scalar(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        )
        return member

    async def list_members(
        self, session: AsyncSession, team_id: uuid.UUID, after_id: uuid.UUID | None, limit: int
    ) -> list[TeamMember]:
        query = select(TeamMember).where(TeamMember.team_id == team_id)
        if after_id is not None:
            query = query.where(TeamMember.id > after_id)
        members = await session.scalars(query.order_by(TeamMember.id).limit(limit))
        return list(members)

    async def remove_member(self, session: AsyncSession, member_id: uuid.UUID) -> None:
        await session.execute(delete(TeamMember).where(TeamMember.id == member_id))

    async def list_role_grants(
        self, session: AsyncSession, team_id: uuid.UUID
    ) -> list[TeamRoleGrant]:
        """At most one row per workspace role, so the list is naturally bounded."""
        grants = await session.scalars(
            select(TeamRoleGrant)
            .where(TeamRoleGrant.team_id == team_id)
            .order_by(TeamRoleGrant.role)
        )
        return list(grants)

    async def find_role_grant(
        self, session: AsyncSession, team_id: uuid.UUID, role: str
    ) -> TeamRoleGrant | None:
        grant: TeamRoleGrant | None = await session.scalar(
            select(TeamRoleGrant).where(
                TeamRoleGrant.team_id == team_id, TeamRoleGrant.role == role
            )
        )
        return grant

    async def save_role_grant(self, session: AsyncSession, grant: TeamRoleGrant) -> TeamRoleGrant:
        session.add(grant)
        await session.flush()
        await session.refresh(grant)
        return grant

    async def remove_role_grant(self, session: AsyncSession, grant_id: uuid.UUID) -> None:
        await session.execute(delete(TeamRoleGrant).where(TeamRoleGrant.id == grant_id))
