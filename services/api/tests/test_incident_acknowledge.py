"""Impact-started, detected and acknowledged timestamps (MPS-8A.20, MPS-15.02)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import AMIRA, WORKSPACE_B1, principal_for, seed_two_organisations_with_members

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


def _headers(idempotency_key: str | None = None) -> dict[str, str]:
    return {
        "Authorization": "Bearer sub-amira",
        WORKSPACE_HEADER: str(WORKSPACE_B1),
        "Idempotency-Key": idempotency_key or f"idem-{uuid.uuid4()}",
    }


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _declare(client: TestClient, **body: Any) -> Any:
    return client.post(
        INCIDENTS, headers=_headers(), json={"title": "Times", "severity": "sev2", **body}
    )


def _acknowledge(client: TestClient, incident_id: str, key: str | None = None) -> Any:
    return client.post(f"{INCIDENTS}/{incident_id}/acknowledge", headers=_headers(key))


def test_declare_records_reported_times_and_defaults_detection(client: TestClient) -> None:
    impact = datetime.now(UTC) - timedelta(minutes=20)
    detected = datetime.now(UTC) - timedelta(minutes=10)

    explicit = _declare(client, impact_started_at=_iso(impact), detected_at=_iso(detected))
    defaulted = _declare(client).json()["data"]

    data = explicit.json()["data"]
    assert explicit.status_code == 201
    assert datetime.fromisoformat(data["impact_started_at"]) == impact
    assert datetime.fromisoformat(data["detected_at"]) == detected
    assert defaulted["impact_started_at"] is None
    assert defaulted["detected_at"] is not None
    assert (defaulted["acknowledged_at"], defaulted["acknowledged_by_user_id"]) == (None, None)


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"detected_at": "2099-01-01T00:00:00Z"}, "INCIDENT_TIMESTAMP_IN_FUTURE"),
        ({"impact_started_at": "2099-01-01T00:00:00Z"}, "INCIDENT_TIMESTAMP_IN_FUTURE"),
        (
            {"impact_started_at": "2026-01-02T00:00:00Z", "detected_at": "2026-01-01T00:00:00Z"},
            "INCIDENT_IMPACT_AFTER_DETECTION",
        ),
    ],
)
def test_implausible_reported_times_are_rejected(
    client: TestClient, body: dict[str, str], code: str
) -> None:
    response = _declare(client, **body)

    assert (response.status_code, response.json()["code"]) == (422, code)


def test_naive_timestamps_are_rejected(client: TestClient) -> None:
    assert _declare(client, detected_at="2026-01-01T00:00:00").status_code == 422


def test_reported_times_can_be_corrected_and_are_on_the_timeline(client: TestClient) -> None:
    incident = _declare(client, detected_at="2026-01-01T10:00:00Z").json()["data"]
    path = f"{INCIDENTS}/{incident['id']}"

    corrected = client.patch(
        path, headers=_headers(), json={"impact_started_at": "2026-01-01T09:30:00Z"}
    )
    too_late = client.patch(
        path, headers=_headers(), json={"impact_started_at": "2026-01-01T10:30:00Z"}
    )
    unchanged = client.patch(path, headers=_headers(), json={"detected_at": "2026-01-01T10:00:00Z"})

    assert corrected.status_code == 200
    assert too_late.json()["code"] == "INCIDENT_IMPACT_AFTER_DETECTION"
    assert unchanged.json()["code"] == "INCIDENT_NO_CHANGES"
    update = client.get(f"{path}/timeline", headers=_headers()).json()["data"][-1]
    assert (update["kind"], update["before"], update["after"]) == (
        "incident.updated",
        {"impact_started_at": None},
        {"impact_started_at": "2026-01-01T09:30:00+00:00"},
    )


def test_acknowledge_once_records_who_and_when(client: TestClient) -> None:
    incident_id = _declare(client).json()["data"]["id"]

    first = _acknowledge(client, incident_id)
    second = _acknowledge(client, incident_id)

    data = first.json()["data"]
    assert first.status_code == 200
    assert data["acknowledged_by_user_id"] == str(AMIRA)
    assert data["acknowledged_at"] is not None
    assert first.headers["etag"]
    assert (second.status_code, second.json()["code"]) == (409, "INCIDENT_ALREADY_ACKNOWLEDGED")
    kinds = [
        event["kind"]
        for event in client.get(f"{INCIDENTS}/{incident_id}/timeline", headers=_headers()).json()[
            "data"
        ]
    ]
    assert kinds == ["incident.declared", "incident.acknowledged"]


def test_acknowledge_retry_with_same_key_replays(client: TestClient) -> None:
    incident_id = _declare(client).json()["data"]["id"]
    key = f"idem-{uuid.uuid4()}"

    first = _acknowledge(client, incident_id, key)
    retry = _acknowledge(client, incident_id, key)

    assert (retry.status_code, retry.json()) == (200, first.json())


def test_only_worked_incidents_can_be_acknowledged(client: TestClient) -> None:
    cancelled = _declare(client).json()["data"]["id"]
    client.post(
        f"{INCIDENTS}/{cancelled}/transitions",
        headers=_headers(),
        json={"target_state": "cancelled", "reason": "False alarm"},
    )

    refused = _acknowledge(client, cancelled)
    unknown = _acknowledge(client, str(uuid.uuid4()))
    draft = _acknowledge(client, _declare(client, is_declared=False).json()["data"]["id"])

    assert (refused.status_code, refused.json()["code"]) == (409, "INCIDENT_NOT_ACKNOWLEDGEABLE")
    assert unknown.json()["code"] == "INCIDENT_NOT_FOUND"
    assert draft.status_code == 200
