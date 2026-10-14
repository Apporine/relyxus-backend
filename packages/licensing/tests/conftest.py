from typing import Any

import pytest

CUSTOMER_ID = "6f1c3a52-2d4e-4b7a-9c1e-3f5a7b9d0e21"
LICENSE_ID = "0b7e2f64-81c9-4d3a-a5f2-9e4c6d8b1a37"
DEPLOYMENT_ID = "acme-bank-prod-eu"


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
