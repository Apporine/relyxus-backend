"""Queries for identities and role grants. No access rules here (context.md §1)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.model import User, WorkspaceMembership
from relyxus_api.shared.db.transaction_settings import set_transaction_settings

IDP_ISSUER_SETTING = "app.idp_issuer"
IDP_SUBJECT_SETTING = "app.idp_subject"
USER_SETTING = "app.user_id"


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

    async def list_workspace_grants(
        self, session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> list[WorkspaceMembership]:
        # RLS only reveals this user's own grants until a tenant context is applied.
        await set_transaction_settings(session, {USER_SETTING: str(user_id)})
        memberships = await session.scalars(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        return list(memberships)
