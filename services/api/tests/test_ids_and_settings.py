import time
import uuid

import pytest
from pydantic import ValidationError

from api_test_support import make_settings
from relyxus_api.shared.utils.ids import new_uuid7


def test_uuid7_has_version_and_variant() -> None:
    identifier = new_uuid7()

    assert identifier.version == 7
    assert identifier.variant == uuid.RFC_4122


def test_uuid7_embeds_current_millisecond_timestamp() -> None:
    before = time.time_ns() // 1_000_000
    identifier = new_uuid7()
    after = time.time_ns() // 1_000_000

    assert before <= identifier.int >> 80 <= after


def test_uuid7_sorts_by_creation_time_and_is_unique() -> None:
    earlier = new_uuid7()
    time.sleep(0.002)
    later = new_uuid7()

    assert earlier < later
    assert len({new_uuid7() for _ in range(1000)}) == 1000


def test_database_url_is_never_shown() -> None:
    settings = make_settings(database_url="postgresql+psycopg://app:hunter2@db:5432/relyxus")

    assert "hunter2" not in repr(settings)
    assert "hunter2" not in str(settings.model_dump())


@pytest.mark.parametrize(
    "database_url", ["postgresql://app@db/relyxus", "mysql://app@db/relyxus", ""]
)
def test_database_url_must_use_psycopg_driver(database_url: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(database_url=database_url)
