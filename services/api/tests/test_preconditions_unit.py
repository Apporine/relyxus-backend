import pytest

from relyxus_api.shared.errors.app_errors import PreconditionFailedError
from relyxus_api.shared.http.preconditions import assert_if_match


def test_assert_if_match_allows_matching_etag() -> None:
    assert_if_match('W/"abc"', 'W/"abc"')


def test_assert_if_match_rejects_mismatch() -> None:
    with pytest.raises(PreconditionFailedError):
        assert_if_match('W/"abc"', 'W/"def"')
