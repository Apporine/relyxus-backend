"""Licence lifecycle states (LIC §7) and the offline state evaluation (ADR-0002 §7)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from apporine_licensing.errors import UnsupportedGracePolicyError


class LicenseState(StrEnum):
    """All LIC §7 states. Offline verification can only yield ACTIVE, GRACE or EXPIRED.

    DRAFT never reaches a customer; SUSPENDED and REVOKED come only from signed status
    refresh (connected mode); SUPERSEDED is assigned by the local licence store.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    GRACE = "grace"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class GracePolicy:
    policy_id: str
    grace_period: timedelta


# Provisional registry (register Q-07b): MPS-6A.11 states a 30-day grace after expiry.
GRACE_POLICIES = {
    policy.policy_id: policy for policy in [GracePolicy("standard-30d", timedelta(days=30))]
}


def find_grace_policy(policy_id: str) -> GracePolicy:
    policy = GRACE_POLICIES.get(policy_id)
    if policy is None:
        raise UnsupportedGracePolicyError("Licence grace_policy_id is not supported")
    return policy


def evaluate_state(expires_at: datetime, grace_policy: GracePolicy, now: datetime) -> LicenseState:
    """Commercial expiry is a state, never an error: it must not stop safety functions."""
    if now <= expires_at:
        return LicenseState.ACTIVE
    if now <= expires_at + grace_policy.grace_period:
        return LicenseState.GRACE
    return LicenseState.EXPIRED
