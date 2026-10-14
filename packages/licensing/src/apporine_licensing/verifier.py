"""Offline licence verifier (LIC §20 phase 2; ADR-0002 §6).

Runs entirely locally: no network access and no issuer dependency (LIC-2.04, MPS-29.11).
Untrustworthy artifacts fail closed with a typed error; commercial expiry fails safe by
being reported as a state (DEP-23.08, MPS-29.04).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from apporine_licensing.envelope import parse_envelope
from apporine_licensing.errors import (
    CustomerMismatchError,
    DeploymentNotLicensedError,
    LicenseNotYetValidError,
    LicenseTooLargeError,
    ProductMismatchError,
    SigningKeyWindowError,
)
from apporine_licensing.key_set import KeyEnvironment, TrustedKeySet
from apporine_licensing.license_state import LicenseState, evaluate_state, find_grace_policy
from apporine_licensing.payload import DeploymentBinding, LicensePayload, parse_payload
from apporine_licensing.signature import authenticate_envelope

DEFAULT_MAX_ARTIFACT_BYTES = 64 * 1024
DEFAULT_CLOCK_SKEW_TOLERANCE = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class InstallationIdentity:
    """What this installation is; licences must be bound to it (MPS-29.17)."""

    product_id: str
    customer_id: str
    deployment_id: str
    environment: KeyEnvironment


@dataclass(frozen=True, slots=True)
class VerificationPolicy:
    max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES
    clock_skew_tolerance: timedelta = DEFAULT_CLOCK_SKEW_TOLERANCE


@dataclass(frozen=True, slots=True)
class VerifiedLicense:
    payload: LicensePayload
    signing_key_id: str
    deployment_binding: DeploymentBinding
    state: LicenseState
    grace_ends_at: datetime
    evaluated_at: datetime

    def has_entitlement(self, key: str) -> bool:
        """Commercial capabilities only; universal security is never gated (LIC-13.01)."""
        return key in self.payload.entitlements

    def get_limit(self, key: str) -> int | None:
        return self.payload.limits.get(key)


@dataclass(frozen=True, slots=True)
class LicenseVerifier:
    key_set: TrustedKeySet
    installation: InstallationIdentity
    policy: VerificationPolicy = field(default_factory=VerificationPolicy)

    def verify(self, artifact: bytes, now: datetime) -> VerifiedLicense:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if len(artifact) > self.policy.max_artifact_bytes:
            raise LicenseTooLargeError("Licence file exceeds the maximum accepted size")

        envelope = parse_envelope(artifact)
        authenticated = authenticate_envelope(envelope, self.key_set, self.installation.environment)
        payload = parse_payload(authenticated.payload_bytes)
        binding = self._match_installation(payload)

        if not authenticated.signing_key.can_have_issued_at(payload.issued_at):
            raise SigningKeyWindowError("Licence issue time is outside its signing key's window")
        if payload.not_before > now + self.policy.clock_skew_tolerance:
            raise LicenseNotYetValidError("Licence is not valid yet")

        grace_policy = find_grace_policy(payload.grace_policy_id)
        return VerifiedLicense(
            payload=payload,
            signing_key_id=authenticated.signing_key.key_id,
            deployment_binding=binding,
            state=evaluate_state(payload.expires_at, grace_policy, now),
            grace_ends_at=payload.expires_at + grace_policy.grace_period,
            evaluated_at=now,
        )

    def _match_installation(self, payload: LicensePayload) -> DeploymentBinding:
        if payload.product_id != self.installation.product_id:
            raise ProductMismatchError("Licence is for a different product")
        if payload.customer_id != self.installation.customer_id:
            raise CustomerMismatchError("Licence is for a different customer")
        for binding in payload.deployment_bindings:
            if binding.deployment_id == self.installation.deployment_id:
                return binding
        raise DeploymentNotLicensedError("Licence does not cover this deployment")
