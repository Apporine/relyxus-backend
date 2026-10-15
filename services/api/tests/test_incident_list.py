"""Incident list (MPS-15.02): newest first, filters, cursor paging, workspace isolation."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    WORKSPACE_A1,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
INCIDENTS = "/api/v1/incidents"
COMMANDER = ("sub-amira", WORKSPACE_B1)
OTHER_WORKSPACE = ("sub-amira", WORKSPACE_A1)
VIEWER_ELSEWHERE = ("sub-bob", WORKSPACE_B1)


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)
    run_as_superuser(url, seed_two_organisations_with_members)
    return url


class _SubjectTokenVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture(scope="module")
def client(database_url: str) -> TestClient:
    app = create_app(make_settings(database_url=database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    return TestClient(app)


def _headers(actor: tuple[str, uuid.UUID]) -> dict[str, str]:
    subject, workspace = actor
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
    }


def _create(
    client: TestClient,
    title: str,
    severity: str,
    *,
    is_declared: bool = True,
    actor: tuple[str, uuid.UUID] = COMMANDER,
) -> str:
    response = client.post(
        INCIDENTS,
        headers=_headers(actor),
        json={"title": title, "severity": severity, "is_declared": is_declared},
    )
    assert response.status_code == 201, response.text
    incident_id: str = response.json()["data"]["id"]
    return incident_id


@pytest.fixture(scope="module")
def created(client: TestClient) -> dict[str, str]:
    ids = {
        "oldest": _create(client, "Disk filling", "sev4"),
        "draft": _create(client, "Maybe DNS", "sev3", is_declared=False),
        "major": _create(client, "Payments down", "sev1"),
        "newest": _create(client, "Latency", "sev2"),
    }
    _create(client, "Other workspace", "sev1", actor=OTHER_WORKSPACE)
    return ids


def _list(client: TestClient, query: str = "", actor: tuple[str, uuid.UUID] = COMMANDER) -> Any:
    return client.get(f"{INCIDENTS}{query}", headers=_headers(actor))


def test_lists_only_this_workspace_newest_first(
    client: TestClient, created: dict[str, str]
) -> None:
    body = _list(client).json()

    assert [item["id"] for item in body["data"]] == [
        created["newest"],
        created["major"],
        created["draft"],
        created["oldest"],
    ]
    assert "total" not in body["meta"]


def test_filters_by_state_and_severity(client: TestClient, created: dict[str, str]) -> None:
    triage = _list(client, "?lifecycle_state=triage").json()["data"]
    severe = _list(client, "?severity=sev1&severity=sev2").json()["data"]
    both = _list(client, "?lifecycle_state=investigating&severity=sev4").json()["data"]

    assert [item["id"] for item in triage] == [created["draft"]]
    assert {item["id"] for item in severe} == {created["major"], created["newest"]}
    assert [item["id"] for item in both] == [created["oldest"]]


def test_cursor_walk_returns_each_incident_once(
    client: TestClient, created: dict[str, str]
) -> None:
    seen: list[str] = []
    query = "?limit=3"
    while True:
        body = _list(client, query).json()
        seen.extend(item["id"] for item in body["data"])
        if body["meta"]["next_cursor"] is None:
            break
        query = f"?limit=3&cursor={body['meta']['next_cursor']}"

    assert seen == [created["newest"], created["major"], created["draft"], created["oldest"]]


def test_any_workspace_member_can_read(client: TestClient, created: dict[str, str]) -> None:
    assert _list(client, actor=VIEWER_ELSEWHERE).status_code == 200


@pytest.mark.parametrize(
    "query", ["?lifecycle_state=open", "?severity=critical", "?limit=0", "?cursor=garbage!!"]
)
def test_invalid_queries_are_rejected(client: TestClient, query: str) -> None:
    assert _list(client, query).status_code == 422
