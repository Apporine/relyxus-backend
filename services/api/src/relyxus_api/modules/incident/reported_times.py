"""Rules for the people-reported metric timestamps: impact started and detected (MPS-8A.20).

MTTR runs from impact started to resolved by default, so these values feed reporting and
must be plausible: never in the future (beyond a small clock-skew allowance) and impact
never starting after it was detected. The database enforces the ordering too.
"""

from datetime import UTC, datetime, timedelta
from typing import ClassVar

from relyxus_api.shared.errors.app_errors import ValidationFailedError

CLOCK_SKEW_ALLOWANCE = timedelta(minutes=1)


class IncidentTimestampInFutureError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_TIMESTAMP_IN_FUTURE"


class ImpactAfterDetectionError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_IMPACT_AFTER_DETECTION"


def validate_reported_times(
    impact_started_at: datetime | None, detected_at: datetime | None, now: datetime
) -> None:
    for name, value in (("impact_started_at", impact_started_at), ("detected_at", detected_at)):
        if value is not None and value > now + CLOCK_SKEW_ALLOWANCE:
            raise IncidentTimestampInFutureError(f"{name} cannot be in the future.")
    if impact_started_at and detected_at and impact_started_at > detected_at:
        raise ImpactAfterDetectionError("Impact cannot start after the incident was detected.")


def isoformat_or_none(value: datetime | None) -> str | None:
    """UTC ISO 8601, so audit and timeline values do not depend on the session time zone."""
    return None if value is None else value.astimezone(UTC).isoformat()
