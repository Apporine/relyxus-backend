"""Tenant context for PostgreSQL row-level security (MP-10.01, MPS-28.08, TSD-22.02/22.03).

With no context set, every RLS policy matches nothing: access fails closed.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.shared.db.transaction_settings import set_transaction_settings

ORGANIZATION_SETTING = "app.organization_id"
WORKSPACE_SETTING = "app.workspace_id"


@dataclass(frozen=True, slots=True)
class TenantContext:
    """A verified tenant scope. Build it only from authenticated membership, never from
    client-supplied identifiers alone (MP-10.01, MPS-28.10)."""

    organization_id: uuid.UUID
    workspace_id: uuid.UUID | None = None


async def apply_tenant_context(session: AsyncSession, context: TenantContext) -> None:
    workspace = "" if context.workspace_id is None else str(context.workspace_id)
    await set_transaction_settings(
        session,
        {ORGANIZATION_SETTING: str(context.organization_id), WORKSPACE_SETTING: workspace},
    )
