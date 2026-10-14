from datetime import UTC, datetime, timedelta

import pytest

from apporine_licensing.errors import UnsupportedGracePolicyError
from apporine_licensing.license_state import LicenseState, evaluate_state, find_grace_policy

EXPIRES_AT = datetime(2027, 10, 1, tzinfo=UTC)
STANDARD = find_grace_policy("standard-30d")


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (EXPIRES_AT - timedelta(days=1), LicenseState.ACTIVE),
        (EXPIRES_AT, LicenseState.ACTIVE),
        (EXPIRES_AT + timedelta(seconds=1), LicenseState.GRACE),
        (EXPIRES_AT + timedelta(days=30), LicenseState.GRACE),
        (EXPIRES_AT + timedelta(days=30, seconds=1), LicenseState.EXPIRED),
        (EXPIRES_AT + timedelta(days=3650), LicenseState.EXPIRED),
    ],
)
def test_state_boundaries(now: datetime, expected: LicenseState) -> None:
    assert evaluate_state(EXPIRES_AT, STANDARD, now) is expected


def test_standard_grace_is_thirty_days() -> None:
    assert STANDARD.grace_period == timedelta(days=30)


def test_unknown_grace_policy_is_unsupported() -> None:
    with pytest.raises(UnsupportedGracePolicyError):
        find_grace_policy("forever")
