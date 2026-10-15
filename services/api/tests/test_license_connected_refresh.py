"""Connected refresh merges signed remote status into licence status (LIC-10.03)."""

from datetime import UTC, datetime

from cryptography.hazmat.primitives.asymmetric import ec

from apporine_licensing.connected_refresh import ConnectedRefreshPolicy
from apporine_licensing.key_set import KeyEnvironment, TrustedKeySet
from apporine_licensing.license_state import LicenseState
from apporine_licensing.payload import LicensePayload
from apporine_licensing.verifier import InstallationIdentity, LicenseVerifier, VerifiedLicense
from relyxus_api.modules.license.service import (
    ConnectedRefreshConfig,
    LicenseRuntime,
    LicenseService,
    LicenseStatusCache,
)
from signing_support import (
    CUSTOMER_ID,
    DEPLOYMENT_ID,
    LICENSE_ID,
    make_trusted_key,
    sign_status_snapshot,
)

KEY_ID = "connected-refresh-test-1"
NOW = datetime(2027, 6, 1, 12, 0, tzinfo=UTC)


def _verified_license() -> VerifiedLicense:
    payload = LicensePayload.model_validate(
        {
            "schema_version": 1,
            "license_id": LICENSE_ID,
            "revision": 2,
            "customer_id": CUSTOMER_ID,
            "product_id": "relyxus",
            "deployment_bindings": [
                {"deployment_id": DEPLOYMENT_ID, "allowance": "production"},
            ],
            "issued_at": "2026-10-01T09:00:00Z",
            "not_before": "2026-10-01T00:00:00Z",
            "expires_at": "2027-10-01T00:00:00Z",
            "grace_policy_id": "standard-30d",
            "entitlements": ["relyxus.premium_connectors"],
            "limits": {},
            "support_tier": "standard",
        }
    )
    return VerifiedLicense(
        payload=payload,
        signing_key_id=KEY_ID,
        deployment_binding=payload.deployment_bindings[0],
        state=LicenseState.ACTIVE,
        grace_ends_at=payload.expires_at,
        evaluated_at=NOW,
    )


def test_live_revoked_snapshot_overrides_offline_active() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    trusted_key = make_trusted_key(private_key, KEY_ID)
    installation = InstallationIdentity(
        product_id="relyxus",
        customer_id=CUSTOMER_ID,
        deployment_id=DEPLOYMENT_ID,
        environment=KeyEnvironment.PRODUCTION,
    )
    key_set = TrustedKeySet([trusted_key])
    runtime = LicenseRuntime(
        verifier=LicenseVerifier(key_set, installation),
        key_set=key_set,
        installation=installation,
    )
    document = sign_status_snapshot(
        private_key,
        KEY_ID,
        license_id=LICENSE_ID,
        revision=2,
        commercial_status="revoked",
    )
    cache = LicenseStatusCache()
    connected = ConnectedRefreshConfig(
        status_url="https://licensing.example.test/status",
        fetch_timeout_seconds=1.0,
        policy=ConnectedRefreshPolicy(),
        cache=cache,
        fetch=lambda _url, _timeout: document,
    )

    merged, source = LicenseService._apply_connected_refresh(
        runtime,
        _verified_license(),
        LicenseState.ACTIVE,
        NOW,
        connected,
    )

    assert merged is LicenseState.REVOKED
    assert source == "live"
    assert cache.entry is not None
