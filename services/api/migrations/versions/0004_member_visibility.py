"""Let users see the organisations and workspaces they are members of.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-14

The workspace picker (MPS-15.02) lists a user's workspaces across organisations before any
tenant is chosen. Reads widen to "your tenant OR a workspace/organisation you hold a role
in"; writes still require tenant context (WITH CHECK is unchanged).

Rollout: replaces two policies in place; the previous release sees the same or more rows
only for its own members, so it runs unchanged.
Rollback plan: downgrade restores the 0002 policies.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MEMBER_OF_ORGANIZATION = (
    "EXISTS (SELECT 1 FROM workspace_memberships m"
    " WHERE m.organization_id = organizations.id AND m.user_id = relyxus_current_user_id())"
)
_MEMBER_OF_WORKSPACE = (
    "EXISTS (SELECT 1 FROM workspace_memberships m"
    " WHERE m.workspace_id = workspaces.id AND m.user_id = relyxus_current_user_id())"
)
_POLICIES = {
    "organizations": ("id", _MEMBER_OF_ORGANIZATION),
    "workspaces": ("organization_id", _MEMBER_OF_WORKSPACE),
}


def _replace_policy(table: str, column: str, extra_visibility: str | None) -> None:
    op.execute(f"DROP POLICY {table}_tenant_isolation ON {table}")
    visibility = f"{column} = relyxus_current_organization_id()"
    if extra_visibility is not None:
        visibility = f"{visibility} OR {extra_visibility}"
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table}"
        f" USING ({visibility})"
        f" WITH CHECK ({column} = relyxus_current_organization_id())"
    )


def upgrade() -> None:
    for table, (column, membership_clause) in _POLICIES.items():
        _replace_policy(table, column, membership_clause)


def downgrade() -> None:
    for table, (column, _membership_clause) in _POLICIES.items():
        _replace_policy(table, column, None)
