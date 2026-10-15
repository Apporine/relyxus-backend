"""The incident visibility rule, applied to every incident read (MPS-8A.23, MPS-8A.24).

One predicate, used by `IncidentRepository` for finding, locking and listing incidents.
Every incident sub-resource (tasks, timeline, roles, review, ...) is reached through
those reads, so an incident the caller may not see is a 404 everywhere, exactly like an
incident that does not exist: "someone without access cannot learn the incident exists".

A caller sees an incident when any of these holds (register Q-42):
- its visibility is `workspace`;
- they hold the workspace owner role ("can do everything", MPS-14.02);
- they created or declared it, or hold one of its incident roles (IC, comms, scribe);
- they hold an unexpired person grant;
- the incident is `restricted` and they hold an unexpired team grant (as a team member)
  or role grant (holding that workspace role).
With no viewer on the session the rule fails closed to `workspace` incidents only.
"""

from datetime import UTC, datetime

from sqlalchemy import ColumnElement, and_, exists, false, or_, select, true

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.access.viewer import Viewer
from relyxus_api.modules.incident.access_grant_model import IncidentAccessGrant
from relyxus_api.modules.incident.model import Incident, IncidentVisibility
from relyxus_api.modules.incident.role_model import IncidentRoleAssignment


def visible_to(viewer: Viewer | None) -> ColumnElement[bool]:
    is_workspace_wide = Incident.visibility == IncidentVisibility.WORKSPACE.value
    if viewer is None:
        return is_workspace_wide
    if WorkspaceRole.OWNER in viewer.roles:
        return true()
    unexpired = or_(
        IncidentAccessGrant.expires_at.is_(None),
        IncidentAccessGrant.expires_at > datetime.now(UTC),
    )
    group_grant = or_(
        IncidentAccessGrant.team_id.in_(viewer.team_ids) if viewer.team_ids else false(),
        IncidentAccessGrant.role.in_([role.value for role in viewer.roles]),
    )
    granted = exists(
        select(IncidentAccessGrant.id).where(
            IncidentAccessGrant.incident_id == Incident.id,
            unexpired,
            or_(
                IncidentAccessGrant.user_id == viewer.user_id,
                and_(Incident.visibility == IncidentVisibility.RESTRICTED.value, group_grant),
            ),
        )
    )
    holds_incident_role = exists(
        select(IncidentRoleAssignment.id).where(
            IncidentRoleAssignment.incident_id == Incident.id,
            IncidentRoleAssignment.user_id == viewer.user_id,
        )
    )
    return or_(
        is_workspace_wide,
        Incident.created_by_user_id == viewer.user_id,
        Incident.declared_by_user_id == viewer.user_id,
        holds_incident_role,
        granted,
    )
