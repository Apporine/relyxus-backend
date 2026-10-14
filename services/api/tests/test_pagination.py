from dataclasses import dataclass

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from api_test_support import make_settings
from relyxus_api.app import create_app
from relyxus_api.shared.http.envelope import ListEnvelope, wrap_page
from relyxus_api.shared.http.pagination import (
    MAX_PAGE_LIMIT,
    InvalidCursorError,
    PageRequest,
    PageRequestDependency,
    build_page,
    decode_cursor,
    encode_cursor,
)


@dataclass(frozen=True)
class Item:
    number: int


NUMBERS = list(range(1, 46))


@pytest.fixture
def client() -> TestClient:
    app = create_app(make_settings())
    router = APIRouter()

    @router.get("/numbers")
    def list_numbers(page_request: PageRequestDependency) -> ListEnvelope[int]:
        after = int(page_request.after[0]) if page_request.after else 0
        fetched = [n for n in NUMBERS if n > after][: page_request.limit + 1]
        return wrap_page(build_page(fetched, page_request, lambda n: (n,)))

    app.include_router(router)
    return TestClient(app)


def test_cursor_round_trips_mixed_positions() -> None:
    position = ("2026-10-14T09:00:00Z", 42, "0192f0c4-7d1e-7a3b-9c2d-5e6f7a8b9c0d")

    assert decode_cursor(encode_cursor(position)) == position


@pytest.mark.parametrize(
    "cursor",
    [
        "not-base64-!!",
        encode_cursor(("x",))[:-3],
        "eyJ2IjoyLCJwIjpbMV19",  # version 2
        "eyJ2IjoxLCJwIjpbdHJ1ZV19",  # boolean position
        "eyJ2IjoxLCJwIjoiYSJ9",  # position not a list
        "W10",  # JSON array, not object
        "é",
    ],
)
def test_tampered_or_foreign_cursors_are_rejected(cursor: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor)


def test_build_page_sets_cursor_only_when_more_rows_exist() -> None:
    request = PageRequest(after=None, limit=2)

    full = build_page([Item(1), Item(2), Item(3)], request, lambda item: (item.number,))
    last = build_page([Item(1)], request, lambda item: (item.number,))
    empty: list[Item] = []
    empty_page = build_page(empty, request, lambda item: (item.number,))

    assert [item.number for item in full.items] == [1, 2]
    assert full.next_cursor is not None
    assert decode_cursor(full.next_cursor) == (2,)
    assert last.next_cursor is None
    assert list(empty_page.items) == []
    assert empty_page.next_cursor is None


def test_walking_cursors_returns_every_item_exactly_once(client: TestClient) -> None:
    seen: list[int] = []
    url = "/numbers?limit=20"
    while True:
        body = client.get(url).json()
        seen.extend(body["data"])
        assert set(body) == {"success", "data", "meta"}
        assert "total" not in body["meta"]
        if body["meta"]["next_cursor"] is None:
            break
        url = f"/numbers?limit=20&cursor={body['meta']['next_cursor']}"

    assert seen == NUMBERS


def test_default_limit_is_twenty(client: TestClient) -> None:
    body = client.get("/numbers").json()

    assert len(body["data"]) == 20
    assert body["meta"]["limit"] == 20


@pytest.mark.parametrize("limit", [0, MAX_PAGE_LIMIT + 1, -5])
def test_limit_outside_bounds_is_a_validation_problem(client: TestClient, limit: int) -> None:
    response = client.get(f"/numbers?limit={limit}")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"


def test_invalid_cursor_is_a_specific_problem(client: TestClient) -> None:
    response = client.get("/numbers?cursor=garbage!!")

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_CURSOR"
