"""End-to-end offline verification cases required by TSD-23.14, LIC-19.02 and DEP-23.08."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from apporine_licensing.canonical_json import canonicalize
from apporine_licensing.errors import (
    CustomerMismatchError,
    DeploymentNotLicensedError,
    LicenseNotYetValidError,
    LicenseTooLargeError,
    LicenseVerificationError,
    ProductMismatchError,
    SigningKeyWindowError,
    UnknownSigningKeyError,
    UnsupportedGracePolicyError,
)
from apporine_licensing.key_set import KeyEnvironment, TrustedKey, TrustedKeySet
from apporine_licensing.license_state import LicenseState
from apporine_licensing.payload import DeploymentAllowance
from apporine_licensing.verifier import InstallationIdentity, LicenseVerifier, VerificationPolicy
from signing_support import (
    CUSTOMER_ID,
    DEPLOYMENT_ID,
    PRODUCTION_KEY_ID,
    make_trusted_key,
    sign_envelope,
)

NOW = datetime(2027, 1, 15, 12, 0, tzinfo=UTC)
INSTALLATION = InstallationIdentity(
    product_id="relyxus",
    customer_id=CUSTOMER_ID,
    deployment_id=DEPLOYMENT_ID,
    environment=KeyEnvironment.PRODUCTION,
)

type Issue = Callable[..., bytes]


@pytest.fixture
def issue(
    production_private_key: ec.EllipticCurvePrivateKey, payload_document: dict[str, Any]
) -> Issue:
    def issue_license(key_id: str = PRODUCTION_KEY_ID, **changes: object) -> bytes:
        payload_document.update(changes)
        return sign_envelope(canonicalize(payload_document), production_private_key, key_id)

    return issue_license


@pytest.fixture
def verifier(production_key: TrustedKey) -> LicenseVerifier:
    return LicenseVerifier(TrustedKeySet([production_key]), INSTALLATION)


def test_valid_licence_verifies_as_active(verifier: LicenseVerifier, issue: Issue) -> None:
    verified = verifier.verify(issue(), NOW)

    assert verified.state is LicenseState.ACTIVE
    assert verified.signing_key_id == PRODUCTION_KEY_ID
    assert verified.deployment_binding.allowance is DeploymentAllowance.PRODUCTION
    assert verified.grace_ends_at == datetime(2027, 10, 31, tzinfo=UTC)
    assert verified.has_entitlement("relyxus.premium_connectors")
    assert not verified.has_entitlement("relyxus.advanced_replay")
    assert verified.get_limit("relyxus.production_deployments") == 1
    assert verified.get_limit("relyxus.seats") is None


def test_disaster_recovery_deployment_is_recognised(
    production_key: TrustedKey, issue: Issue
) -> None:
    dr_installation = InstallationIdentity(
        "relyxus", CUSTOMER_ID, "acme-bank-dr-eu", INSTALLATION.environment
    )

    verified = LicenseVerifier(TrustedKeySet([production_key]), dr_installation).verify(
        issue(), NOW
    )

    assert verified.deployment_binding.allowance is DeploymentAllowance.DISASTER_RECOVERY


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2027, 10, 15, tzinfo=UTC), LicenseState.GRACE),
        (datetime(2028, 1, 1, tzinfo=UTC), LicenseState.EXPIRED),
    ],
)
def test_expiry_is_reported_as_state_not_error(
    verifier: LicenseVerifier, issue: Issue, now: datetime, expected: LicenseState
) -> None:
    assert verifier.verify(issue(), now).state is expected


def test_not_yet_valid_licence_is_rejected(verifier: LicenseVerifier, issue: Issue) -> None:
    with pytest.raises(LicenseNotYetValidError):
        verifier.verify(issue(not_before="2027-02-01T00:00:00Z"), NOW)


def test_clock_skew_tolerance_accepts_slightly_early_start(
    verifier: LicenseVerifier, issue: Issue
) -> None:
    starts_soon = (NOW + timedelta(minutes=4)).strftime("%Y-%m-%dT%H:%M:%SZ")

    assert verifier.verify(issue(not_before=starts_soon), NOW).state is LicenseState.ACTIVE


def test_clock_skew_tolerance_is_configurable(production_key: TrustedKey, issue: Issue) -> None:
    strict = LicenseVerifier(
        TrustedKeySet([production_key]),
        INSTALLATION,
        VerificationPolicy(clock_skew_tolerance=timedelta(0)),
    )
    starts_soon = (NOW + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    with pytest.raises(LicenseNotYetValidError):
        strict.verify(issue(not_before=starts_soon), NOW)


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"customer_id": "11111111-2222-4333-8444-555555555555"}, CustomerMismatchError),
        (
            {
                "deployment_bindings": [
                    {"deployment_id": "other-bank-prod", "allowance": "production"}
                ]
            },
            DeploymentNotLicensedError,
        ),
        (
            {"product_id": "futureproduct", "entitlements": [], "limits": {}},
            ProductMismatchError,
        ),
        ({"grace_policy_id": "forever"}, UnsupportedGracePolicyError),
        (
            {"issued_at": "2025-12-31T23:59:59Z", "not_before": "2025-12-31T00:00:00Z"},
            SigningKeyWindowError,
        ),
    ],
)
def test_licence_not_bound_to_this_installation_is_rejected(
    verifier: LicenseVerifier, issue: Issue, changes: dict[str, object], error: type[Exception]
) -> None:
    with pytest.raises(error):
        verifier.verify(issue(**changes), NOW)


def test_wrong_key_is_rejected(verifier: LicenseVerifier, issue: Issue) -> None:
    with pytest.raises(UnknownSigningKeyError):
        verifier.verify(issue(key_id="apporine-license-unknown"), NOW)


def test_tampered_artifact_is_rejected(verifier: LicenseVerifier, issue: Issue) -> None:
    artifact = issue()
    tampered = artifact.replace(b'"signature":"', b'"signature":"A', 1)

    with pytest.raises(LicenseVerificationError):
        verifier.verify(tampered, NOW)


def test_licence_from_retired_key_is_rejected_after_issue_window(
    production_private_key: ec.EllipticCurvePrivateKey, issue: Issue
) -> None:
    retired = make_trusted_key(
        production_private_key, PRODUCTION_KEY_ID, valid_until=datetime(2026, 6, 30, tzinfo=UTC)
    )
    verifier = LicenseVerifier(TrustedKeySet([retired]), INSTALLATION)

    with pytest.raises(SigningKeyWindowError):
        verifier.verify(issue(), NOW)


def test_rotated_key_licence_verifies_alongside_old_key(
    production_key: TrustedKey,
    other_private_key: ec.EllipticCurvePrivateKey,
    payload_document: dict[str, Any],
) -> None:
    rotated = make_trusted_key(other_private_key, "apporine-license-test-prod-2")
    verifier = LicenseVerifier(TrustedKeySet([production_key, rotated]), INSTALLATION)
    artifact = sign_envelope(canonicalize(payload_document), other_private_key, rotated.key_id)

    assert verifier.verify(artifact, NOW).signing_key_id == rotated.key_id


def test_oversized_artifact_is_rejected_before_parsing(
    production_key: TrustedKey, issue: Issue
) -> None:
    verifier = LicenseVerifier(
        TrustedKeySet([production_key]), INSTALLATION, VerificationPolicy(max_artifact_bytes=64)
    )

    with pytest.raises(LicenseTooLargeError):
        verifier.verify(issue(), NOW)


def test_naive_clock_is_a_programming_error(verifier: LicenseVerifier, issue: Issue) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        verifier.verify(issue(), datetime(2027, 1, 15))  # noqa: DTZ001
