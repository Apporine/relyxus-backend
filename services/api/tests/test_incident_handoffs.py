"""Incident role handoffs (MPS-11.23, MPS-11.24, MPS-20.33)."""

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
from relyxus_api.modules.incident.handoff_model import IncidentRoleHandoff
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


def _incident_with_commander(client: TestClient) -> str:
    incident_id: str = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Handoff", "severity": "sev1"}
    ).json()["data"]["id"]
    client.put(
        f"{INCIDENTS}/{incident_id}/roles/incident_commander",
        headers=_headers(),
        json={"user_id": str(AMIRA)},
    )
    return incident_id


def _request(
    client: TestClient,
    incident_id: str,
    to_user: uuid.UUID = BOB,
    role: str = "incident_commander",
    subject: str = "sub-amira",
) -> Any:
    return client.post(
        f"{INCIDENTS}/{incident_id}/handoffs",
        headers=_headers(subject),
        json={"role": role, "to_user_id": str(to_user)},
    )


def _act(
    client: TestClient,
    incident_id: str,
    handoff_id: str,
    action: str,
    subject: str = "sub-bob",
    key: str | None = None,
) -> Any:
    return client.post(
        f"{INCIDENTS}/{incident_id}/handoffs/{handoff_id}/{action}",
        headers=_headers(subject, key),
    )


def _commander(client: TestClient, incident_id: str) -> str | None:
    roles = client.get(f"{INCIDENTS}/{incident_id}/roles", headers=_headers()).json()["data"]
    holders = [item["user_id"] for item in roles if item["role"] == "incident_commander"]
    return holders[0] if holders else None


def test_handoff_moves_the_role_only_when_accepted(client: TestClient) -> None:
    incident_id = _incident_with_commander(client)
    tasks = f"{INCIDENTS}/{incident_id}/tasks"
    client.post(
        tasks, headers=_headers(), json={"title": "Fail over", "due_at": "2026-10-15T09:00:00Z"}
    )
    done = client.post(tasks, headers=_headers(), json={"title": "Page vendor"}).json()["data"]
    client.patch(f"{tasks}/{done['id']}", headers=_headers(), json={"status": "done"})

    requested = _request(client, incident_id)
    handoff = requested.json()["data"]
    assert requested.status_code == 201
    assert (handoff["state"], handoff["from_user_id"], handoff["to_user_id"]) == (
        "pending",
        str(AMIRA),
        str(BOB),
    )
    package = handoff["package"]
    assert package["incident"]["severity"] == "sev1"
    assert [task["title"] for task in package["open_tasks"]] == ["Fail over"]
    assert package["roles"] == [{"role": "incident_commander", "user_id": str(AMIRA)}]
    assert "pending_approvals" in package["unavailable_sections"]
    assert _commander(client, incident_id) == str(AMIRA)

    accepted = _act(client, incident_id, handoff["id"], "accept")

    assert accepted.json()["data"]["state"] == "accepted"
    assert accepted.json()["data"]["accepted_at"] is not None
    assert _commander(client, incident_id) == str(BOB)
    events = client.get(f"{INCIDENTS}/{incident_id}/timeline", headers=_headers()).json()["data"]
    accepted_event = events[-1]
    assert [event["kind"] for event in events[-2:]] == [
        "incident.handoff_requested",
        "incident.handoff_accepted",
    ]
    assert accepted_event["actor_user_id"] == str(BOB)
    assert accepted_event["before"] == {"role": "incident_commander", "user_id": str(AMIRA)}
    assert (accepted_event["after"]["from_user_id"], accepted_event["after"]["to_user_id"]) == (
        str(AMIRA),
        str(BOB),
    )


def test_only_the_incoming_person_can_accept(client: TestClient) -> None:
    incident_id = _incident_with_commander(client)
    handoff_id = _request(client, incident_id).json()["data"]["id"]

    response = _act(client, incident_id, handoff_id, "accept", subject="sub-amira")

    assert (response.status_code, response.json()["code"]) == (
        403,
        "INCIDENT_HANDOFF_NOT_RECIPIENT",
    )


def test_request_rules(client: TestClient) -> None:
    incident_id = _incident_with_commander(client)

    no_holder = _request(client, incident_id, role="scribe")
    same_person = _request(client, incident_id, to_user=AMIRA)
    not_member = _request(client, incident_id, to_user=SUSPENDED)
    first = _request(client, incident_id)
    second = _request(client, incident_id)

    assert (no_holder.status_code, no_holder.json()["code"]) == (
        409,
        "INCIDENT_HANDOFF_NO_CURRENT_HOLDER",
    )
    assert same_person.json()["code"] == "INCIDENT_HANDOFF_SAME_PERSON"
    assert not_member.json()["code"] == "INCIDENT_ROLE_ASSIGNEE_NOT_MEMBER"
    assert first.status_code == 201
    assert (second.status_code, second.json()["code"]) == (409, "INCIDENT_HANDOFF_ALREADY_PENDING")


def test_only_holder_or_role_manager_can_request(client: TestClient) -> None:
    incident_id = _incident_with_commander(client)
    client.put(
        f"{INCIDENTS}/{incident_id}/roles/scribe", headers=_headers(), json={"user_id": str(AMIRA)}
    )

    by_admin = _request(client, incident_id, to_user=BOB, role="scribe", subject="sub-bob")

    assert (by_admin.status_code, by_admin.json()["code"]) == (403, "INSUFFICIENT_WORKSPACE_ROLE")


def test_incoming_person_can_decline(client: TestClient) -> None:
    incident_id = _incident_with_commander(client)
    handoff_id = _request(client, incident_id).json()["data"]["id"]

    declined = _act(client, incident_id, handoff_id, "cancel")
    accept_after = _act(client, incident_id, handoff_id, "accept")

    data = declined.json()["data"]
    assert (data["state"], data["cancelled_by_user_id"]) == ("cancelled", str(BOB))
    assert (accept_after.status_code, accept_after.json()["code"]) == (
        409,
        "INCIDENT_HANDOFF_NOT_PENDING",
    )
    assert _commander(client, incident_id) == str(AMIRA)
    assert _request(client, incident_id).status_code == 201


def test_stale_handoff_cannot_be_accepted(client: TestClient) -> None:
    incident_id = _incident_with_commander(client)
    handoff_id = _request(client, incident_id).json()["data"]["id"]
    client.put(
        f"{INCIDENTS}/{incident_id}/roles/incident_commander",
        headers=_headers(),
        json={"user_id": str(BOB)},
    )

    response = _act(client, incident_id, handoff_id, "accept")

    assert (response.status_code, response.json()["code"]) == (409, "INCIDENT_HANDOFF_STALE")


def test_accept_retry_replays_and_list_shows_history(client: TestClient) -> None:
    incident_id = _incident_with_commander(client)
    handoff_id = _request(client, incident_id).json()["data"]["id"]
    key = f"idem-{uuid.uuid4()}"

    first = _act(client, incident_id, handoff_id, "accept", key=key)
    retry = _act(client, incident_id, handoff_id, "accept", key=key)

    assert (retry.status_code, retry.json()) == (200, first.json())
    listed = client.get(f"{INCIDENTS}/{incident_id}/handoffs", headers=_headers()).json()
    assert [(item["id"], item["state"]) for item in listed["data"]] == [(handoff_id, "accepted")]


def test_unknown_handoff_and_frozen_incident(client: TestClient) -> None:
    incident_id = _incident_with_commander(client)
    unknown = _act(client, incident_id, str(uuid.uuid4()), "accept")
    client.post(
        f"{INCIDENTS}/{incident_id}/transitions",
        headers=_headers(),
        json={"target_state": "cancelled", "reason": "Duplicate"},
    )

    frozen = _request(client, incident_id)

    assert (unknown.status_code, unknown.json()["code"]) == (404, "INCIDENT_HANDOFF_NOT_FOUND")
    assert (frozen.status_code, frozen.json()["code"]) == (409, "INCIDENT_NOT_EDITABLE")


def test_handoffs_are_tenant_isolated(client: TestClient, database_url: str) -> None:
    _request(client, _incident_with_commander(client))

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(IncidentRoleHandoff.id))).all())

    assert run_as_probe_role(database_url, visible) == 0
