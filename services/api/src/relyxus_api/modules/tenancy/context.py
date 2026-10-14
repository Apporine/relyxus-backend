"""Tenant context for PostgreSQL row-level security (MP-10.01, MPS-28.08, TSD-22.02/22.03).

The context is set with `set_config(..., is_local => true)`, so it lives only for the
current transaction and can never leak to another request reusing a pooled connection.
With no context set, every RLS policy matches nothing: access fails closed.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ORGANIZATION_SETTING = "app.organization_id"
WORKSPACE_SETTING = "app.workspace_id"
_SET_LOCAL = text("SELECT set_config(:name, :value, true)")


@dataclass(frozen=True, slots=True)
class TenantContext:
    """A verified tenant scope. Build it only from authenticated membership, never from
    client-supplied identifiers alone (MP-10.01, MPS-28.10)."""

    organization_id: uuid.UUID
    workspace_id: uuid.UUID | None = None


async def apply_tenant_context(session: AsyncSession, context: TenantContext) -> None:
    if not session.in_transaction():
        raise RuntimeError("Tenant context must be applied inside a transaction")
    workspace = "" if context.workspace_id is None else str(context.workspace_id)
    await session.execute(
        _SET_LOCAL, {"name": ORGANIZATION_SETTING, "value": str(context.organization_id)}
    )
    await session.execute(_SET_LOCAL, {"name": WORKSPACE_SETTING, "value": workspace})
