"""Incident lifecycle states and transition rules (MPS-8A.07, ADR-0004)."""

from enum import StrEnum
from typing import ClassVar

from relyxus_api.shared.errors.app_errors import ConflictError


class IncidentLifecycleState(StrEnum):
    TRIAGE = "triage"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    MERGED = "merged"


OPEN_LIFECYCLE_STATES = frozenset(
    {
        IncidentLifecycleState.TRIAGE,
        IncidentLifecycleState.INVESTIGATING,
        IncidentLifecycleState.MITIGATING,
        IncidentLifecycleState.MONITORING,
        IncidentLifecycleState.RESOLVED,
    }
)

TERMINAL_LIFECYCLE_STATES = frozenset(
    {
        IncidentLifecycleState.CLOSED,
        IncidentLifecycleState.CANCELLED,
        IncidentLifecycleState.MERGED,
    }
)

_ALLOWED_TRANSITIONS: dict[IncidentLifecycleState, frozenset[IncidentLifecycleState]] = {
    IncidentLifecycleState.TRIAGE: frozenset(
        {
            IncidentLifecycleState.INVESTIGATING,
            IncidentLifecycleState.CANCELLED,
            IncidentLifecycleState.MERGED,
        }
    ),
    IncidentLifecycleState.INVESTIGATING: frozenset(
        {
            IncidentLifecycleState.MITIGATING,
            IncidentLifecycleState.CANCELLED,
            IncidentLifecycleState.MERGED,
        }
    ),
    IncidentLifecycleState.MITIGATING: frozenset(
        {
            IncidentLifecycleState.MONITORING,
            IncidentLifecycleState.CANCELLED,
            IncidentLifecycleState.MERGED,
        }
    ),
    IncidentLifecycleState.MONITORING: frozenset(
        {
            IncidentLifecycleState.RESOLVED,
            IncidentLifecycleState.MITIGATING,
            IncidentLifecycleState.CANCELLED,
            IncidentLifecycleState.MERGED,
        }
    ),
    IncidentLifecycleState.RESOLVED: frozenset(
        {
            IncidentLifecycleState.CLOSED,
            IncidentLifecycleState.INVESTIGATING,
        }
    ),
    IncidentLifecycleState.CLOSED: frozenset(),
    IncidentLifecycleState.CANCELLED: frozenset(),
    IncidentLifecycleState.MERGED: frozenset(),
}


class InvalidIncidentLifecycleTransitionError(ConflictError):
    code: ClassVar[str] = "INCIDENT_INVALID_LIFECYCLE_TRANSITION"


def validate_lifecycle_transition(
    current: IncidentLifecycleState, target: IncidentLifecycleState
) -> None:
    """Reject transitions that are not allowed by ADR-0004."""
    if current is target:
        return
    allowed = _ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidIncidentLifecycleTransitionError(
            f"Cannot move an incident from {current.value} to {target.value}."
        )
