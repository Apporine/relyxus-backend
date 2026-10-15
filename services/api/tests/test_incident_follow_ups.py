"""Post-incident follow-ups (MPS-26.02, MPS-13.17)."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_test_support import make_settings
from db_test_support import (
    migrate_and_reset,
    require_test_database_url,
    run_as_probe_role,
    run_as_superuser,
)
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.modules.incident.follow_up_model import IncidentFollowUp
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    AMIRA,
    BOB,
    ORG_A,
    SUSPENDED,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
INCIDENTS = "/api/v1/incidents"
RESOLVE_PATH = ("mitigating", "monitoring", "resolved")


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


def _headers(key: str | None = None) -> dict[str, str]:
    return {
        "Authorization": "Bearer sub-amira",
        WORKSPACE_HEADER: str(WORKSPACE_B1),
        "Idempotency-Key": key or f"idem-{uuid.uuid4()}",
    }


def _incident(client: TestClient, severity: str = "sev2", *, resolved: bool = True) -> str:
    incident_id: str = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Follow-ups", "severity": severity}
    ).json()["data"]["id"]
    for state in RESOLVE_PATH if resolved else ():
        client.post(
            f"{INCIDENTS}/{incident_id}/transitions",
            headers=_headers(),
            json={"target_state": state},
        )
    return incident_id


def _create(client: TestClient, incident_id: str, key: str | None = None, **body: Any) -> Any:
    return client.post(
        f"{INCIDENTS}/{incident_id}/follow-ups",
        headers=_headers(key),
        json={"title": "Add card-processor alerting", **body},
    )


def _patch(client: TestClient, incident_id: str, follow_up_id: str, body: dict[str, Any]) -> Any:
    return client.patch(
        f"{INCIDENTS}/{incident_id}/follow-ups/{follow_up_id}", headers=_headers(), json=body
    )


@pytest.mark.parametrize(
    ("severity", "mandatory"), [("sev1", True), ("sev2", True), ("sev3", False)]
)
def test_mandatory_defaults_by_severity(client: TestClient, severity: str, mandatory: bool) -> None:
    response = _create(client, _incident(client, severity))

    data = response.json()["data"]
    assert response.status_code == 201
    assert (data["is_mandatory"], data["status"], data["source"]) == (mandatory, "open", "manual")
    assert data["source_task_id"] is None


def test_explicit_mandatory_flag_wins(client: TestClient) -> None:
    data = _create(client, _incident(client, "sev1"), is_mandatory=False).json()["data"]

    assert data["is_mandatory"] is False


def test_follow_ups_wait_for_resolution(client: TestClient) -> None:
    response = _create(client, _incident(client, resolved=False))

    assert (response.status_code, response.json()["code"]) == (
        409,
        "INCIDENT_FOLLOW_UPS_NOT_AVAILABLE",
    )


def test_status_flow_owner_rules_and_timeline(client: TestClient) -> None:
    incident_id = _incident(client)
    follow_up_id = _create(client, incident_id, owner_user_id=str(BOB)).json()["data"]["id"]

    assert _patch(client, incident_id, follow_up_id, {"status": "in_progress"}).status_code == 200
    cleared = _patch(client, incident_id, follow_up_id, {"owner_user_id": None}).json()["data"]
    outsider = _patch(client, incident_id, follow_up_id, {"owner_user_id": str(SUSPENDED)})
    done = _patch(client, incident_id, follow_up_id, {"status": "done"}).json()["data"]
    reopened = _patch(client, incident_id, follow_up_id, {"status": "open"})

    assert cleared["owner_user_id"] is None
    assert outsider.json()["code"] == "INCIDENT_FOLLOW_UP_OWNER_NOT_MEMBER"
    assert (done["status"], done["completed_by_user_id"]) == ("done", str(AMIRA))
    assert (reopened.status_code, reopened.json()["code"]) == (
        409,
        "INCIDENT_FOLLOW_UP_NOT_EDITABLE",
    )
    events = client.get(f"{INCIDENTS}/{incident_id}/timeline", headers=_headers()).json()["data"]
    follow_up_events = [event for event in events if event["subject_id"] == follow_up_id]
    assert [event["kind"] for event in follow_up_events] == [
        "incident.follow_up_created",
        "incident.follow_up_updated",
        "incident.follow_up_updated",
        "incident.follow_up_updated",
    ]


def test_cancel_needs_reason_and_no_op_is_rejected(client: TestClient) -> None:
    incident_id = _incident(client)
    follow_up_id = _create(client, incident_id).json()["data"]["id"]

    no_reason = _patch(client, incident_id, follow_up_id, {"status": "cancelled"})
    no_op = _patch(client, incident_id, follow_up_id, {"is_mandatory": True})
    cancelled = _patch(
        client, incident_id, follow_up_id, {"status": "cancelled", "reason": "Covered elsewhere"}
    )

    assert no_reason.json()["code"] == "INCIDENT_FOLLOW_UP_REASON_REQUIRED"
    assert no_op.json()["code"] == "INCIDENT_FOLLOW_UP_NO_CHANGES"
    assert cancelled.json()["data"]["cancellation_reason"] == "Covered elsewhere"


def test_list_paging_retry_and_unknown_ids(client: TestClient) -> None:
    incident_id = _incident(client)
    key = f"idem-{uuid.uuid4()}"
    first = _create(client, incident_id, key)
    retry = _create(client, incident_id, key)
    for index in range(2):
        _create(client, incident_id, title=f"Item {index}")

    page_one = client.get(
        f"{INCIDENTS}/{incident_id}/follow-ups?limit=2", headers=_headers()
    ).json()
    page_two = client.get(
        f"{INCIDENTS}/{incident_id}/follow-ups?limit=2&cursor={page_one['meta']['next_cursor']}",
        headers=_headers(),
    ).json()
    unknown = _patch(client, incident_id, str(uuid.uuid4()), {"title": "x"})

    assert retry.json() == first.json()
    assert [item["title"] for item in page_one["data"] + page_two["data"]] == [
        "Add card-processor alerting",
        "Item 0",
        "Item 1",
    ]
    assert unknown.json()["code"] == "INCIDENT_FOLLOW_UP_NOT_FOUND"


def test_follow_ups_are_tenant_isolated(client: TestClient, database_url: str) -> None:
    _create(client, _incident(client))

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(IncidentFollowUp.id))).all())

    assert run_as_probe_role(database_url, visible) == 0
