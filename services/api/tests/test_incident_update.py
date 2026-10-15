"""Edit an incident's title or severity (MPS-8.06, MPS-22A.05)."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.modules.audit.model import AuditEvent
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import WORKSPACE_B1, principal_for, seed_two_organisations_with_members

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


def _headers(**extra: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer sub-amira",
        WORKSPACE_HEADER: str(WORKSPACE_B1),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
        **extra,
    }


def _declare(client: TestClient) -> str:
    response = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Checkout slow", "severity": "sev2"}
    )
    incident_id: str = response.json()["data"]["id"]
    return incident_id


def _patch(client: TestClient, incident_id: str, body: dict[str, Any], **headers: str) -> Any:
    return client.patch(f"{INCIDENTS}/{incident_id}", headers=_headers(**headers), json=body)


def test_title_change_needs_no_reason(client: TestClient) -> None:
    incident_id = _declare(client)

    response = _patch(client, incident_id, {"title": "  Checkout slow in EU  "})

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Checkout slow in EU"
    assert response.headers["etag"]


def test_severity_change_requires_a_reason_and_is_audited(
    client: TestClient, database_url: str
) -> None:
    incident_id = _declare(client)
    assert (
        _patch(client, incident_id, {"severity": "sev1"}).json()["code"]
        == "INCIDENT_SEVERITY_REASON_REQUIRED"
    )

    response = _patch(
        client, incident_id, {"severity": "sev1", "reason": "Failures above 500 a minute"}
    )
    assert response.json()["data"]["severity"] == "sev1"

    async def last_event(session: AsyncSession) -> AuditEvent | None:
        event: AuditEvent | None = await session.scalar(
            select(AuditEvent)
            .where(AuditEvent.target_id == incident_id)
            .order_by(AuditEvent.sequence.desc())
            .limit(1)
        )
        return event

    event = run_as_superuser(database_url, last_event)
    assert event is not None
    assert (event.action, event.before_state, event.after_state) == (
        "incident.updated",
        {"severity": "sev2"},
        {"severity": "sev1", "reason": "Failures above 500 a minute"},
    )


@pytest.mark.parametrize(
    "body", [{}, {"title": "Checkout slow"}, {"severity": "sev2", "reason": "same"}]
)
def test_requests_that_change_nothing_are_rejected(
    client: TestClient, body: dict[str, Any]
) -> None:
    response = _patch(client, _declare(client), body)

    assert (response.status_code, response.json()["code"]) == (422, "INCIDENT_NO_CHANGES")


def test_terminal_incidents_cannot_be_changed(client: TestClient) -> None:
    incident_id = _declare(client)
    client.post(
        f"{INCIDENTS}/{incident_id}/transitions",
        headers=_headers(),
        json={"target_state": "cancelled", "reason": "dup"},
    )

    response = _patch(client, incident_id, {"title": "Renamed"})

    assert (response.status_code, response.json()["code"]) == (409, "INCIDENT_NOT_EDITABLE")


def test_stale_if_match_is_refused(client: TestClient) -> None:
    incident_id = _declare(client)
    etag = client.get(f"{INCIDENTS}/{incident_id}", headers=_headers()).headers["etag"]
    assert (
        _patch(client, incident_id, {"title": "First edit"}, **{"If-Match": etag}).status_code
        == 200
    )

    stale = _patch(client, incident_id, {"title": "Second edit"}, **{"If-Match": etag})

    assert (stale.status_code, stale.json()["code"]) == (412, "PRECONDITION_FAILED")


def test_admin_can_edit_but_non_members_cannot(client: TestClient) -> None:
    incident_id = _declare(client)
    headers = {"Authorization": "Bearer sub-bob", WORKSPACE_HEADER: str(WORKSPACE_B1)}
    assert (
        client.patch(
            f"{INCIDENTS}/{incident_id}", headers=headers, json={"title": "Admin edit"}
        ).status_code
        == 200
    )
    headers[WORKSPACE_HEADER] = str(uuid.uuid4())
    assert (
        client.patch(f"{INCIDENTS}/{incident_id}", headers=headers, json={"title": "x"}).status_code
        == 403
    )


def test_unknown_fields_are_rejected(client: TestClient) -> None:
    response = _patch(client, _declare(client), {"lifecycle_state": "closed"})

    assert response.status_code == 422
