"""Workspace role gates (MPS-14.02-14.09). Ph0 checks until OPA owns these decisions."""

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


# MPS-14: incident commanders run incidents and responders investigate; viewers and
# auditors may never change state.
_INCIDENT_WRITE_ROLES = frozenset(
    {
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.INCIDENT_COMMANDER,
        WorkspaceRole.RESPONDER,
    }
)


async def require_incident_write_access(
    workspace: WorkspaceSessionDependency,
) -> AsyncIterator[WorkspaceSession]:
    if not _INCIDENT_WRITE_ROLES.intersection(workspace.access.roles):
        raise InsufficientWorkspaceRoleError(
            "This workspace role cannot create or change incidents."
        )
    yield workspace


IncidentWriteWorkspaceDependency = Annotated[
    WorkspaceSession, Depends(require_incident_write_access, scope="function")
]


# MPS-14.02: "Admin — users, teams, connectors, settings"; the owner can do everything.
_WORKSPACE_STRUCTURE_ROLES = frozenset({WorkspaceRole.OWNER, WorkspaceRole.ADMIN})


async def require_workspace_structure_access(
    workspace: WorkspaceSessionDependency,
) -> AsyncIterator[WorkspaceSession]:
    if not _WORKSPACE_STRUCTURE_ROLES.intersection(workspace.access.roles):
        raise InsufficientWorkspaceRoleError(
            "Only workspace owners and admins can change workspace configuration."
        )
    yield workspace


WorkspaceStructureDependency = Annotated[
    WorkspaceSession, Depends(require_workspace_structure_access, scope="function")
]


async def require_workspace_owner(
    workspace: WorkspaceSessionDependency,
) -> AsyncIterator[WorkspaceSession]:
    """Role grants can hand out any role, including owner, so only owners make them (Q-40)."""
    if WorkspaceRole.OWNER not in workspace.access.roles:
        raise InsufficientWorkspaceRoleError("Only workspace owners can grant roles.")
    yield workspace


WorkspaceOwnerDependency = Annotated[
    WorkspaceSession, Depends(require_workspace_owner, scope="function")
]
