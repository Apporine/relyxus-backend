"""Idempotent replay for POST /audit-events (ADR-0003 §5)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import WORKSPACE_A1, principal_for, seed_two_organisations_with_members

pytestmark = pytest.mark.integration


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


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer sub-amira",
        WORKSPACE_HEADER: str(WORKSPACE_A1),
        "Idempotency-Key": key,
    }


def _body(action: str = "incident.declare") -> dict[str, object]:
    return {
        "action": action,
        "target_type": "incident",
        "target_id": str(uuid.uuid4()),
        "outcome": "succeeded",
        "after_state": {"status": "triage"},
    }


def test_post_audit_event_replays_with_same_idempotency_key(client: TestClient) -> None:
    key = f"idem-{uuid.uuid4()}"
    payload = _body()
    first = client.post("/api/v1/audit-events", headers=_headers(key), json=payload)
    second = client.post("/api/v1/audit-events", headers=_headers(key), json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()


def test_idempotency_key_reuse_with_different_body_is_conflict(client: TestClient) -> None:
    key = f"idem-{uuid.uuid4()}"
    client.post("/api/v1/audit-events", headers=_headers(key), json=_body("first.action"))
    response = client.post(
        "/api/v1/audit-events", headers=_headers(key), json=_body("second.action")
    )

    assert response.status_code == 409
    assert response.json()["code"] == "IDEMPOTENCY_KEY_REUSE"
