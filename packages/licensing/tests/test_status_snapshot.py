"""Signed commercial status snapshots (LIC-9.03, LIC-10.02)."""

import json

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from apporine_licensing.errors import CustomerMismatchError, SignatureInvalidError
from apporine_licensing.key_set import KeyEnvironment, TrustedKeySet
from apporine_licensing.status_snapshot import CommercialStatus, verify_status_snapshot
from apporine_licensing.verifier import InstallationIdentity
from signing_support import (
    CUSTOMER_ID,
    DEPLOYMENT_ID,
    PRODUCTION_KEY_ID,
    make_trusted_key,
    sign_status_snapshot,
)

INSTALLATION = InstallationIdentity(
    product_id="relyxus",
    customer_id=CUSTOMER_ID,
    deployment_id=DEPLOYMENT_ID,
    environment=KeyEnvironment.PRODUCTION,
)


def test_verify_status_snapshot_accepts_valid_document(
    production_private_key: ec.EllipticCurvePrivateKey, production_key
) -> None:
    document = sign_status_snapshot(
        production_private_key,
        PRODUCTION_KEY_ID,
        commercial_status="suspended",
    )
    key_set = TrustedKeySet([production_key])

    verified = verify_status_snapshot(
        document, key_set, KeyEnvironment.PRODUCTION, INSTALLATION
    )

    assert verified.payload.commercial_status is CommercialStatus.SUSPENDED
    assert verified.signing_key_id == PRODUCTION_KEY_ID


def test_unsigned_or_tampered_snapshot_is_rejected(
    production_private_key: ec.EllipticCurvePrivateKey, production_key
) -> None:
    envelope = json.loads(sign_status_snapshot(production_private_key, PRODUCTION_KEY_ID))
    envelope["signature"] = envelope["signature"][::-1]
    document = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    key_set = TrustedKeySet([production_key])

    with pytest.raises(SignatureInvalidError):
        verify_status_snapshot(document, key_set, KeyEnvironment.PRODUCTION, INSTALLATION)


def test_snapshot_must_match_installation_customer(
    production_private_key: ec.EllipticCurvePrivateKey, production_key
) -> None:
    document = sign_status_snapshot(
        production_private_key,
        PRODUCTION_KEY_ID,
        customer_id="00000000-0000-4000-8000-000000000099",
    )
    key_set = TrustedKeySet([production_key])

    with pytest.raises(CustomerMismatchError):
        verify_status_snapshot(document, key_set, KeyEnvironment.PRODUCTION, INSTALLATION)
