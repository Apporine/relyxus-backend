"""Unfinished live tasks become follow-ups at resolution (MPS-11.21, MPS-20.32)."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import BOB, WORKSPACE_B1, principal_for, seed_two_organisations_with_members

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


def _headers(key: str | None = None) -> dict[str, str]:
    return {
        "Authorization": "Bearer sub-amira",
        WORKSPACE_HEADER: str(WORKSPACE_B1),
        "Idempotency-Key": key or f"idem-{uuid.uuid4()}",
    }


def _move(client: TestClient, incident_id: str, *states: str) -> None:
    for state in states:
        client.post(
            f"{INCIDENTS}/{incident_id}/transitions",
            headers=_headers(),
            json={"target_state": state},
        )


def _incident_with_task(client: TestClient, severity: str = "sev1") -> tuple[str, str]:
    incident_id = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Convert", "severity": severity}
    ).json()["data"]["id"]
    task_id = client.post(
        f"{INCIDENTS}/{incident_id}/tasks",
        headers=_headers(),
        json={
            "title": "Rotate processor keys",
            "owner_user_id": str(BOB),
            "due_at": "2026-11-02T10:00:00Z",
        },
    ).json()["data"]["id"]
    return incident_id, task_id


def _convert(
    client: TestClient, incident_id: str, task_id: str, key: str | None = None, **body: Any
) -> Any:
    return client.post(
        f"{INCIDENTS}/{incident_id}/tasks/{task_id}/follow-up", headers=_headers(key), json=body
    )


def test_unfinished_task_becomes_a_follow_up(client: TestClient) -> None:
    incident_id, task_id = _incident_with_task(client)
    _move(client, incident_id, "mitigating", "monitoring", "resolved")

    response = _convert(client, incident_id, task_id)

    follow_up = response.json()["data"]
    assert response.status_code == 201
    assert (follow_up["title"], follow_up["owner_user_id"], follow_up["due_at"]) == (
        "Rotate processor keys",
        str(BOB),
        "2026-11-02T10:00:00Z",
    )
    assert (follow_up["source"], follow_up["source_task_id"], follow_up["is_mandatory"]) == (
        "live_task",
        task_id,
        True,
    )
    task = client.get(f"{INCIDENTS}/{incident_id}/tasks", headers=_headers()).json()["data"][0]
    assert (task["status"], task["cancellation_reason"]) == (
        "cancelled",
        "Moved to a follow-up at resolution.",
    )
    kinds = [
        event["kind"]
        for event in client.get(f"{INCIDENTS}/{incident_id}/timeline", headers=_headers()).json()[
            "data"
        ]
    ]
    assert kinds[-2:] == ["incident.task_updated", "incident.follow_up_created"]


def test_conversion_only_while_resolved(client: TestClient) -> None:
    open_incident, open_task = _incident_with_task(client)
    cancelled_incident, cancelled_task = _incident_with_task(client)
    client.post(
        f"{INCIDENTS}/{cancelled_incident}/transitions",
        headers=_headers(),
        json={"target_state": "cancelled", "reason": "Duplicate"},
    )

    too_early = _convert(client, open_incident, open_task)
    too_late = _convert(client, cancelled_incident, cancelled_task)

    assert (too_early.status_code, too_early.json()["code"]) == (
        409,
        "INCIDENT_FOLLOW_UPS_NOT_AVAILABLE",
    )
    assert too_late.json()["code"] == "INCIDENT_FOLLOW_UPS_NOT_AVAILABLE"


def test_finished_or_converted_tasks_cannot_convert(client: TestClient) -> None:
    incident_id, task_id = _incident_with_task(client, "sev3")
    done_id = client.post(
        f"{INCIDENTS}/{incident_id}/tasks", headers=_headers(), json={"title": "Done already"}
    ).json()["data"]["id"]
    client.patch(
        f"{INCIDENTS}/{incident_id}/tasks/{done_id}", headers=_headers(), json={"status": "done"}
    )
    _move(client, incident_id, "mitigating", "monitoring", "resolved")

    first = _convert(client, incident_id, task_id, is_mandatory=True)
    again = _convert(client, incident_id, task_id)
    done = _convert(client, incident_id, done_id)
    unknown = _convert(client, incident_id, str(uuid.uuid4()))

    assert first.json()["data"]["is_mandatory"] is True
    for response in (again, done):
        assert (response.status_code, response.json()["code"]) == (
            409,
            "INCIDENT_TASK_NOT_EDITABLE",
        )
    assert unknown.json()["code"] == "INCIDENT_TASK_NOT_FOUND"


def test_retry_replays_and_status_filter_lists_unfinished(client: TestClient) -> None:
    incident_id, task_id = _incident_with_task(client)
    blocked_id = client.post(
        f"{INCIDENTS}/{incident_id}/tasks", headers=_headers(), json={"title": "Blocked"}
    ).json()["data"]["id"]
    client.patch(
        f"{INCIDENTS}/{incident_id}/tasks/{blocked_id}",
        headers=_headers(),
        json={"status": "blocked"},
    )
    _move(client, incident_id, "mitigating", "monitoring", "resolved")
    key = f"idem-{uuid.uuid4()}"

    first = _convert(client, incident_id, task_id, key)
    retry = _convert(client, incident_id, task_id, key)
    unfinished = client.get(
        f"{INCIDENTS}/{incident_id}/tasks?status=open&status=in_progress&status=blocked",
        headers=_headers(),
    ).json()["data"]

    assert retry.json() == first.json()
    assert [task["id"] for task in unfinished] == [blocked_id]
