"""Live incident tasks (MPS-11.14-11.22)."""

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
from relyxus_api.modules.audit.model import AuditEvent
from relyxus_api.modules.incident.task_model import IncidentTask
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


def _headers(**extra: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer sub-amira",
        WORKSPACE_HEADER: str(WORKSPACE_B1),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
        **extra,
    }


def _incident(client: TestClient) -> str:
    response = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Tasks test", "severity": "sev1"}
    )
    incident_id: str = response.json()["data"]["id"]
    return incident_id


def _create(client: TestClient, incident_id: str, **body: Any) -> Any:
    payload = {"title": "Check database replicas", **body}
    return client.post(f"{INCIDENTS}/{incident_id}/tasks", headers=_headers(), json=payload)


def _patch(
    client: TestClient, incident_id: str, task_id: str, body: dict[str, Any], **headers: str
) -> Any:
    return client.patch(
        f"{INCIDENTS}/{incident_id}/tasks/{task_id}", headers=_headers(**headers), json=body
    )


def test_create_defaults_and_unassigned_flag(client: TestClient) -> None:
    response = _create(client, _incident(client))

    data = response.json()["data"]
    assert response.status_code == 201
    assert (data["status"], data["priority"], data["source"]) == ("open", "medium", "manual")
    assert data["owner_user_id"] is None
    assert data["is_unassigned"] is True


def test_status_flow_records_completion_and_audits_changes(
    client: TestClient, database_url: str
) -> None:
    incident_id = _incident(client)
    task_id = _create(client, incident_id, owner_user_id=str(BOB), priority="high").json()["data"][
        "id"
    ]

    for status in ("in_progress", "blocked", "in_progress"):
        assert _patch(client, incident_id, task_id, {"status": status}).status_code == 200
    done = _patch(client, incident_id, task_id, {"status": "done"}).json()["data"]
    assert done["completed_at"] is not None
    assert done["completed_by_user_id"] == str(AMIRA)

    async def audit(session: AsyncSession) -> list[AuditEvent]:
        rows = await session.scalars(
            select(AuditEvent).where(AuditEvent.target_id == task_id).order_by(AuditEvent.sequence)
        )
        return list(rows)

    events = run_as_superuser(database_url, audit)
    assert [event.action for event in events] == ["incident.task_created"] + [
        "incident.task_updated"
    ] * 4
    assert (events[-1].before_state, events[-1].after_state) == (
        {"status": "in_progress"},
        {"status": "done"},
    )


def test_done_and_cancelled_tasks_are_final(client: TestClient) -> None:
    incident_id = _incident(client)
    done = _create(client, incident_id).json()["data"]["id"]
    _patch(client, incident_id, done, {"status": "done"})
    cancelled = _create(client, incident_id).json()["data"]["id"]

    assert (
        _patch(client, incident_id, cancelled, {"status": "cancelled"}).json()["code"]
        == "INCIDENT_TASK_REASON_REQUIRED"
    )
    assert (
        _patch(
            client, incident_id, cancelled, {"status": "cancelled", "reason": "Not needed"}
        ).status_code
        == 200
    )
    for task_id in (done, cancelled):
        response = _patch(client, incident_id, task_id, {"status": "open"})
        assert (response.status_code, response.json()["code"]) == (
            409,
            "INCIDENT_TASK_NOT_EDITABLE",
        )


def test_owner_can_be_set_and_cleared_but_must_be_a_member(client: TestClient) -> None:
    incident_id = _incident(client)
    task_id = _create(client, incident_id).json()["data"]["id"]

    assert _patch(client, incident_id, task_id, {"owner_user_id": str(BOB)}).json()["data"][
        "owner_user_id"
    ] == str(BOB)
    cleared = _patch(client, incident_id, task_id, {"owner_user_id": None}).json()["data"]
    assert (cleared["owner_user_id"], cleared["is_unassigned"]) == (None, True)
    for outsider in (SUSPENDED, uuid.uuid4()):
        response = _patch(client, incident_id, task_id, {"owner_user_id": str(outsider)})
        assert response.json()["code"] == "INCIDENT_TASK_OWNER_NOT_MEMBER"
    assert _create(client, incident_id, owner_user_id=str(SUSPENDED)).status_code == 422


def test_no_op_and_stale_updates_are_rejected(client: TestClient) -> None:
    incident_id = _incident(client)
    created = _create(client, incident_id)
    task_id, etag = created.json()["data"]["id"], created.headers["etag"]

    assert (
        _patch(client, incident_id, task_id, {"priority": "medium"}).json()["code"]
        == "INCIDENT_TASK_NO_CHANGES"
    )
    assert (
        _patch(client, incident_id, task_id, {"title": "Renamed"}, **{"If-Match": etag}).status_code
        == 200
    )
    assert (
        _patch(client, incident_id, task_id, {"title": "Again"}, **{"If-Match": etag}).status_code
        == 412
    )


def test_tasks_follow_the_incident(client: TestClient, database_url: str) -> None:
    incident_id = _incident(client)
    _create(client, incident_id)
    other = _incident(client)

    unknown = client.get(f"{INCIDENTS}/{uuid.uuid4()}/tasks", headers=_headers())
    wrong_parent = _patch(
        client, other, _create(client, incident_id).json()["data"]["id"], {"title": "x"}
    )
    client.post(
        f"{INCIDENTS}/{incident_id}/transitions",
        headers=_headers(),
        json={"target_state": "cancelled", "reason": "dup"},
    )
    frozen = _create(client, incident_id)

    assert unknown.json()["code"] == "INCIDENT_NOT_FOUND"
    assert wrong_parent.json()["code"] == "INCIDENT_TASK_NOT_FOUND"
    assert (frozen.status_code, frozen.json()["code"]) == (409, "INCIDENT_NOT_EDITABLE")

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(IncidentTask.id))).all())

    assert run_as_probe_role(database_url, visible) == 0


def test_list_pages_oldest_first(client: TestClient) -> None:
    incident_id = _incident(client)
    created = [
        _create(client, incident_id, title=f"Task {index}").json()["data"]["id"]
        for index in range(5)
    ]

    first = client.get(f"{INCIDENTS}/{incident_id}/tasks?limit=3", headers=_headers()).json()
    cursor = first["meta"]["next_cursor"]
    second = client.get(
        f"{INCIDENTS}/{incident_id}/tasks?limit=3&cursor={cursor}", headers=_headers()
    ).json()

    assert [item["id"] for item in first["data"] + second["data"]] == created
    assert second["meta"]["next_cursor"] is None


def test_create_is_idempotent(client: TestClient) -> None:
    incident_id = _incident(client)
    headers = _headers()
    path = f"{INCIDENTS}/{incident_id}/tasks"

    first = client.post(path, headers=headers, json={"title": "Once"})
    second = client.post(path, headers=headers, json={"title": "Once"})

    assert second.json() == first.json()
    listed = client.get(path, headers=_headers()).json()["data"]
    assert len(listed) == 1
