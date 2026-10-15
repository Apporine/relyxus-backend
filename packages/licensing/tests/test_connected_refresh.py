"""Connected refresh cache merge rules (LIC-10.03, LIC-19.03)."""

from datetime import UTC, datetime, timedelta

from apporine_licensing.connected_refresh import (
    ConnectedRefreshPolicy,
    StatusCacheEntry,
    merge_connected_state,
)
from apporine_licensing.license_state import LicenseState
from apporine_licensing.status_snapshot import (
    CommercialStatus,
    StatusSnapshotPayload,
    VerifiedStatusSnapshot,
)

NOW = datetime(2027, 6, 1, 12, 0, tzinfo=UTC)
POLICY = ConnectedRefreshPolicy(cache_ttl=timedelta(hours=1), outage_grace=timedelta(hours=24))
LICENSE_ID = "0b7e2f64-81c9-4d3a-a5f2-9e4c6d8b1a37"


def _cache_entry(status: CommercialStatus, *, retrieved_at: datetime) -> StatusCacheEntry:
    payload = StatusSnapshotPayload(
        schema_version=1,
        license_id=LICENSE_ID,
        revision=2,
        customer_id="6f1c3a52-2d4e-4b7a-9c1e-3f5a7b9d0e21",
        product_id="relyxus",
        deployment_id="acme-bank-prod-eu",
        commercial_status=status,
        effective_at=datetime(2027, 1, 15, 12, 0, tzinfo=UTC),
    )
    return StatusCacheEntry(
        snapshot=VerifiedStatusSnapshot(payload=payload, signing_key_id="test-key"),
        retrieved_at=retrieved_at,
    )


def test_fresh_cached_revocation_overrides_active_offline_state() -> None:
    cache = _cache_entry(CommercialStatus.REVOKED, retrieved_at=NOW - timedelta(minutes=30))

    state = merge_connected_state(
        LicenseState.ACTIVE,
        local_license_id=LICENSE_ID,
        local_revision=2,
        cache=cache,
        now=NOW,
        policy=POLICY,
    )

    assert state is LicenseState.REVOKED


def test_stale_cache_beyond_ttl_and_grace_is_ignored() -> None:
    cache = _cache_entry(
        CommercialStatus.SUSPENDED,
        retrieved_at=NOW - POLICY.cache_ttl - POLICY.outage_grace - timedelta(minutes=1),
    )

    state = merge_connected_state(
        LicenseState.ACTIVE,
        local_license_id=LICENSE_ID,
        local_revision=2,
        cache=cache,
        now=NOW,
        policy=POLICY,
    )

    assert state is LicenseState.ACTIVE


def test_cache_for_older_revision_does_not_apply() -> None:
    cache = _cache_entry(CommercialStatus.REVOKED, retrieved_at=NOW - timedelta(minutes=5))

    state = merge_connected_state(
        LicenseState.ACTIVE,
        local_license_id=LICENSE_ID,
        local_revision=3,
        cache=cache,
        now=NOW,
        policy=POLICY,
    )

    assert state is LicenseState.ACTIVE
