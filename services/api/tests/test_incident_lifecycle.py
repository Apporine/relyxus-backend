"""Incident lifecycle transition rules (ADR-0004)."""

import pytest

from relyxus_api.modules.incident.lifecycle import (
    IncidentLifecycleState,
    InvalidIncidentLifecycleTransitionError,
    validate_lifecycle_transition,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (IncidentLifecycleState.TRIAGE, IncidentLifecycleState.INVESTIGATING),
        (IncidentLifecycleState.INVESTIGATING, IncidentLifecycleState.MITIGATING),
        (IncidentLifecycleState.MITIGATING, IncidentLifecycleState.MONITORING),
        (IncidentLifecycleState.MONITORING, IncidentLifecycleState.RESOLVED),
        (IncidentLifecycleState.MONITORING, IncidentLifecycleState.MITIGATING),
        (IncidentLifecycleState.RESOLVED, IncidentLifecycleState.CLOSED),
        (IncidentLifecycleState.RESOLVED, IncidentLifecycleState.INVESTIGATING),
        (IncidentLifecycleState.TRIAGE, IncidentLifecycleState.CANCELLED),
        (IncidentLifecycleState.MONITORING, IncidentLifecycleState.MERGED),
    ],
)
def test_allowed_transitions(
    current: IncidentLifecycleState, target: IncidentLifecycleState
) -> None:
    validate_lifecycle_transition(current, target)


def test_same_state_is_a_no_op() -> None:
    validate_lifecycle_transition(IncidentLifecycleState.TRIAGE, IncidentLifecycleState.TRIAGE)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (IncidentLifecycleState.TRIAGE, IncidentLifecycleState.RESOLVED),
        (IncidentLifecycleState.CLOSED, IncidentLifecycleState.INVESTIGATING),
        (IncidentLifecycleState.CANCELLED, IncidentLifecycleState.TRIAGE),
        (IncidentLifecycleState.RESOLVED, IncidentLifecycleState.CANCELLED),
    ],
)
def test_forbidden_transitions_raise(
    current: IncidentLifecycleState, target: IncidentLifecycleState
) -> None:
    with pytest.raises(InvalidIncidentLifecycleTransitionError):
        validate_lifecycle_transition(current, target)
