"""Who may perform each lifecycle transition (MPS-8A.08-8A.16, MPS-14.02-14.09).

Ph0 rules held in code until OPA owns authorisation decisions. The Owner role "can do
everything" (MPS-14.02), so it is included wherever the incident commander is.
"""

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState

_COMMANDER = frozenset({WorkspaceRole.INCIDENT_COMMANDER, WorkspaceRole.OWNER})
_COMMANDER_OR_RESPONDER = _COMMANDER | {WorkspaceRole.RESPONDER}
# Declaring matches the declare endpoint's roles (MPS-8A.08: responder, integration, workflow).
_DECLARERS = _COMMANDER_OR_RESPONDER | {WorkspaceRole.ADMIN}

_STATE = IncidentLifecycleState
_ROLES_BY_TRANSITION: dict[
    tuple[IncidentLifecycleState, IncidentLifecycleState], frozenset[WorkspaceRole]
] = {
    (_STATE.TRIAGE, _STATE.INVESTIGATING): _DECLARERS,  # MPS-8A.08 declare
    (_STATE.INVESTIGATING, _STATE.MITIGATING): _COMMANDER_OR_RESPONDER,  # MPS-8A.09
    (_STATE.MITIGATING, _STATE.MONITORING): _COMMANDER,  # MPS-8A.10
    (_STATE.MONITORING, _STATE.RESOLVED): _COMMANDER,  # MPS-8A.11
    (_STATE.MONITORING, _STATE.MITIGATING): _COMMANDER,  # MPS-8A.13 fix did not hold
    (_STATE.RESOLVED, _STATE.INVESTIGATING): _COMMANDER,  # MPS-8A.14 reopen
}
# MPS-8A.15 / 8A.16: any open state to cancelled or merged, by the incident commander.
_ROLES_BY_TARGET: dict[IncidentLifecycleState, frozenset[WorkspaceRole]] = {
    _STATE.CANCELLED: _COMMANDER,
    _STATE.MERGED: _COMMANDER,
}


def roles_allowed_for(
    current: IncidentLifecycleState, target: IncidentLifecycleState
) -> frozenset[WorkspaceRole]:
    """Empty when no role may perform the move through this API."""
    return _ROLES_BY_TRANSITION.get((current, target)) or _ROLES_BY_TARGET.get(target, frozenset())
