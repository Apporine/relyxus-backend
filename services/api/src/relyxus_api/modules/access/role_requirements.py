"""Workspace role gates for sensitive reads (MPS-14.02)."""

from collections.abc import AsyncIterator
from typing import Annotated, ClassVar

from fastapi import Depends

from relyxus_api.modules.access.dependencies import WorkspaceSession, WorkspaceSessionDependency
from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.shared.errors.app_errors import PermissionDeniedError


class InsufficientWorkspaceRoleError(PermissionDeniedError):
    code: ClassVar[str] = "INSUFFICIENT_WORKSPACE_ROLE"


_AUDIT_READ_ROLES = frozenset(
    {
        WorkspaceRole.AUDITOR,
        WorkspaceRole.COMPLIANCE_OFFICER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.OWNER,
        WorkspaceRole.SECURITY_ADMIN,
    }
)


async def require_audit_read_access(
    workspace: WorkspaceSessionDependency,
) -> AsyncIterator[WorkspaceSession]:
    if not _AUDIT_READ_ROLES.intersection(workspace.access.roles):
        raise InsufficientWorkspaceRoleError("This workspace role cannot read the audit log.")
    yield workspace


AuditReadWorkspaceDependency = Annotated[
    WorkspaceSession, Depends(require_audit_read_access, scope="function")
]
