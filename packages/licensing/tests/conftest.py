"""Shared fixtures; signing helpers live in signing_support.py."""

from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from apporine_licensing.key_set import TrustedKey
from signing_support import (
    CUSTOMER_ID,
    DEPLOYMENT_ID,
    LICENSE_ID,
    PRODUCTION_KEY_ID,
    make_trusted_key,
)


@pytest.fixture(scope="session")
def production_private_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture(scope="session")
def other_private_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def production_key(production_private_key: ec.EllipticCurvePrivateKey) -> TrustedKey:
    return make_trusted_key(production_private_key, PRODUCTION_KEY_ID)


@pytest.fixture
def payload_document() -> dict[str, Any]:
    """A valid v1 payload document; tests mutate copies of it."""
    return {
        "schema_version": 1,
        "license_id": LICENSE_ID,
        "revision": 1,
        "customer_id": CUSTOMER_ID,
        "product_id": "relyxus",
        "deployment_bindings": [
            {"deployment_id": DEPLOYMENT_ID, "allowance": "production"},
            {"deployment_id": "acme-bank-dr-eu", "allowance": "disaster_recovery"},
        ],
        "issued_at": "2026-10-01T09:00:00Z",
        "not_before": "2026-10-01T00:00:00Z",
        "expires_at": "2027-10-01T00:00:00Z",
        "grace_policy_id": "standard-30d",
        "entitlements": ["relyxus.premium_connectors", "relyxus.regulatory_pack_eu_dora"],
        "limits": {"relyxus.production_deployments": 1, "relyxus.non_production_deployments": 2},
        "support_tier": "enterprise",
    }
