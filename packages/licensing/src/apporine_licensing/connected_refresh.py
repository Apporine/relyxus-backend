"""Connected refresh cache and outage behaviour (LIC-10.03, LIC-19.03)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from apporine_licensing.license_state import LicenseState
from apporine_licensing.status_snapshot import CommercialStatus, VerifiedStatusSnapshot


@dataclass(frozen=True, slots=True)
class StatusCacheEntry:
    snapshot: VerifiedStatusSnapshot
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class ConnectedRefreshPolicy:
    """How long a verified snapshot may be reused when the licensing endpoint is unreachable."""

    cache_ttl: timedelta = timedelta(hours=1)
    outage_grace: timedelta = timedelta(hours=24)


def merge_connected_state(
    offline_state: LicenseState,
    *,
    local_license_id: str,
    local_revision: int,
    cache: StatusCacheEntry | None,
    now: datetime,
    policy: ConnectedRefreshPolicy,
) -> LicenseState:
    """Apply a cached signed snapshot when fresh; never weaken offline safety on stale cache."""
    if cache is None:
        return offline_state
    if cache.snapshot.payload.license_id != local_license_id:
        return offline_state
    if cache.snapshot.payload.revision < local_revision:
        return offline_state
    age = now - cache.retrieved_at
    if age > policy.cache_ttl + policy.outage_grace:
        return offline_state
    status = cache.snapshot.payload.commercial_status
    if status is CommercialStatus.REVOKED:
        return LicenseState.REVOKED
    if status is CommercialStatus.SUSPENDED:
        return LicenseState.SUSPENDED
    return offline_state
