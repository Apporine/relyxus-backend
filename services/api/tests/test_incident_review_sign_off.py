"""Required reviewers and sign-offs (MPS-13.13, MPS-13.17)."""

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
    AMIRA,
    BOB,
    SUSPENDED,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
INCIDENTS = "/api/v1/incidents"


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)
    run_as_superuser(url, seed_two_organisations_with_members)
    return url


class _SubjectTokenVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_app(make_settings(database_url=database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    return TestClient(app)


def _headers(subject: str = "sub-amira", key: str | None = None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(WORKSPACE_B1),
        "Idempotency-Key": key or f"idem-{uuid.uuid4()}",
    }


def _resolved(client: TestClient, severity: str, *, with_commander: bool) -> str:
    incident_id: str = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Sign-off", "severity": severity}
    ).json()["data"]["id"]
    if with_commander:
        client.put(
            f"{INCIDENTS}/{incident_id}/roles/incident_commander",
            headers=_headers(),
            json={"user_id": str(AMIRA)},
        )
    for state in ("mitigating", "monitoring", "resolved"):
        client.post(
            f"{INCIDENTS}/{incident_id}/transitions",
            headers=_headers(),
            json={"target_state": state},
        )
    client.patch(
        f"{INCIDENTS}/{incident_id}/review",
        headers=_headers(),
        json={"summary": "What happened.", "lessons_learned": "What we learned."},
    )
    return incident_id


def _path(incident_id: str, suffix: str = "") -> str:
    return f"{INCIDENTS}/{incident_id}/review{suffix}"


def _move(client: TestClient, incident_id: str, target: str) -> Any:
    return client.post(
        _path(incident_id, "/transitions"), headers=_headers(), json={"target_state": target}
    )


def _sign_off(client: TestClient, incident_id: str, subject: str = "sub-amira") -> Any:
    return client.post(_path(incident_id, "/sign-off"), headers=_headers(subject))


def _reviewers(client: TestClient, incident_id: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = client.get(
        _path(incident_id, "/reviewers"), headers=_headers()
    ).json()["data"]
    return data


def test_commander_is_default_reviewer_of_sev1_and_sev2(client: TestClient) -> None:
    sev1 = _resolved(client, "sev1", with_commander=True)
    sev3 = _resolved(client, "sev3", with_commander=True)

    assert [reviewer["user_id"] for reviewer in _reviewers(client, sev1)] == [str(AMIRA)]
    assert _reviewers(client, sev3) == []


def test_approval_waits_for_every_sign_off(client: TestClient) -> None:
    incident_id = _resolved(client, "sev1", with_commander=True)
    client.put(_path(incident_id, f"/reviewers/{BOB}"), headers=_headers())
    _move(client, incident_id, "in_review")

    _sign_off(client, incident_id)
    waiting = _move(client, incident_id, "approved")
    _sign_off(client, incident_id, "sub-bob")
    approved = _move(client, incident_id, "approved")

    assert (waiting.status_code, waiting.json()["code"]) == (
        409,
        "INCIDENT_REVIEW_SIGN_OFFS_MISSING",
    )
    assert str(BOB) in waiting.json()["detail"]
    assert approved.json()["data"]["state"] == "approved"
    assert all(reviewer["signed_off_at"] for reviewer in _reviewers(client, incident_id))


def test_sev1_without_reviewers_cannot_be_approved(client: TestClient) -> None:
    incident_id = _resolved(client, "sev1", with_commander=False)
    _move(client, incident_id, "in_review")

    response = _move(client, incident_id, "approved")

    assert response.json()["code"] == "INCIDENT_REVIEW_SIGN_OFFS_MISSING"


def test_sev3_without_reviewers_can_be_approved(client: TestClient) -> None:
    incident_id = _resolved(client, "sev3", with_commander=False)
    _move(client, incident_id, "in_review")

    assert _move(client, incident_id, "approved").json()["data"]["state"] == "approved"


def test_sending_back_clears_sign_offs(client: TestClient) -> None:
    incident_id = _resolved(client, "sev2", with_commander=True)
    _move(client, incident_id, "in_review")
    _sign_off(client, incident_id)

    _move(client, incident_id, "draft")

    assert _reviewers(client, incident_id)[0]["signed_off_at"] is None


def test_sign_off_rules(client: TestClient) -> None:
    incident_id = _resolved(client, "sev1", with_commander=True)

    while_draft = _sign_off(client, incident_id)
    _move(client, incident_id, "in_review")
    not_reviewer = _sign_off(client, incident_id, "sub-bob")
    first = _sign_off(client, incident_id)
    again = _sign_off(client, incident_id)

    assert (while_draft.status_code, while_draft.json()["code"]) == (
        409,
        "INCIDENT_REVIEW_SIGN_OFF_NOT_OPEN",
    )
    assert not_reviewer.json()["code"] == "INCIDENT_REVIEW_NOT_A_REVIEWER"
    assert first.json()["data"]["signed_off_at"] is not None
    assert again.json()["code"] == "INCIDENT_REVIEW_ALREADY_SIGNED_OFF"


def test_choosing_reviewers(client: TestClient) -> None:
    incident_id = _resolved(client, "sev3", with_commander=False)

    added = client.put(_path(incident_id, f"/reviewers/{BOB}"), headers=_headers())
    again = client.put(_path(incident_id, f"/reviewers/{BOB}"), headers=_headers())
    by_non_owner = client.put(
        _path(incident_id, f"/reviewers/{AMIRA}"), headers=_headers("sub-bob")
    )
    outsider = client.put(_path(incident_id, f"/reviewers/{SUSPENDED}"), headers=_headers())
    removed = client.delete(_path(incident_id, f"/reviewers/{BOB}"), headers=_headers())
    missing = client.delete(_path(incident_id, f"/reviewers/{BOB}"), headers=_headers())

    assert added.json()["data"]["user_id"] == str(BOB)
    assert again.json() == added.json()
    assert by_non_owner.status_code == 403
    assert outsider.json()["code"] == "INCIDENT_REVIEWER_NOT_MEMBER"
    assert removed.status_code == 204
    assert missing.json()["code"] == "INCIDENT_REVIEWER_NOT_FOUND"
    kinds = [
        event["kind"]
        for event in client.get(f"{INCIDENTS}/{incident_id}/timeline", headers=_headers()).json()[
            "data"
        ]
    ]
    assert kinds[-2:] == ["incident.review_reviewer_added", "incident.review_reviewer_removed"]


def test_reviewers_are_fixed_after_approval(client: TestClient) -> None:
    incident_id = _resolved(client, "sev3", with_commander=False)
    _move(client, incident_id, "in_review")
    _move(client, incident_id, "approved")

    response = client.put(_path(incident_id, f"/reviewers/{BOB}"), headers=_headers())

    assert (response.status_code, response.json()["code"]) == (409, "INCIDENT_REVIEW_NOT_EDITABLE")
