"""Incident timeline (MPS-5.20, MPS-8A.33, MPS-11.20)."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
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
from relyxus_api.modules.incident.timeline_model import IncidentTimelineEvent
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    AMIRA,
    BOB,
    ORG_A,
    WORKSPACE_A1,
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


def _headers(workspace: uuid.UUID = WORKSPACE_B1, **extra: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer sub-amira",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
        **extra,
    }


def _timeline(client: TestClient, incident_id: str, query: str = "") -> Any:
    return client.get(f"{INCIDENTS}/{incident_id}/timeline{query}", headers=_headers())


def test_every_kind_of_change_lands_on_the_timeline_in_order(client: TestClient) -> None:
    incident_id = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Timeline", "severity": "sev2"}
    ).json()["data"]["id"]
    client.patch(
        f"{INCIDENTS}/{incident_id}",
        headers=_headers(),
        json={"severity": "sev1", "reason": "Card payments failing"},
    )
    client.put(
        f"{INCIDENTS}/{incident_id}/roles/scribe", headers=_headers(), json={"user_id": str(BOB)}
    )
    task_id = client.post(
        f"{INCIDENTS}/{incident_id}/tasks", headers=_headers(), json={"title": "Check replicas"}
    ).json()["data"]["id"]
    client.patch(
        f"{INCIDENTS}/{incident_id}/tasks/{task_id}", headers=_headers(), json={"status": "done"}
    )
    client.post(
        f"{INCIDENTS}/{incident_id}/transitions",
        headers=_headers(),
        json={"target_state": "mitigating"},
    )

    events = _timeline(client, incident_id).json()["data"]

    assert [event["kind"] for event in events] == [
        "incident.declared",
        "incident.updated",
        "incident.role_assigned",
        "incident.task_created",
        "incident.task_updated",
        "incident.transitioned",
    ]
    assert {event["actor_user_id"] for event in events} == {str(AMIRA)}
    severity = events[1]
    assert (severity["before"], severity["after"]) == (
        {"severity": "sev2"},
        {"severity": "sev1", "reason": "Card payments failing"},
    )
    task_event = events[4]
    assert (task_event["subject_type"], task_event["subject_id"]) == ("incident_task", task_id)
    assert (task_event["before"], task_event["after"]) == (
        {"status": "open"},
        {"status": "done"},
    )


def test_timeline_matches_the_audit_chain(client: TestClient, database_url: str) -> None:
    incident_id = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Paired", "severity": "sev3"}
    ).json()["data"]["id"]
    client.patch(f"{INCIDENTS}/{incident_id}", headers=_headers(), json={"title": "Renamed"})

    async def audit_actions(session: AsyncSession) -> list[str]:
        rows = await session.scalars(
            select(AuditEvent.action)
            .where(AuditEvent.target_id == incident_id)
            .order_by(AuditEvent.sequence)
        )
        return list(rows)

    timeline = [event["kind"] for event in _timeline(client, incident_id).json()["data"]]
    assert timeline == run_as_superuser(database_url, audit_actions)


def test_rejected_changes_leave_no_timeline_event(client: TestClient) -> None:
    incident_id = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Rejected", "severity": "sev3"}
    ).json()["data"]["id"]

    refused = client.patch(
        f"{INCIDENTS}/{incident_id}", headers=_headers(), json={"severity": "sev1"}
    )

    assert refused.json()["code"] == "INCIDENT_SEVERITY_REASON_REQUIRED"
    assert [event["kind"] for event in _timeline(client, incident_id).json()["data"]] == [
        "incident.declared"
    ]


def test_timeline_pages_oldest_first(client: TestClient) -> None:
    incident_id = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Paged", "severity": "sev3"}
    ).json()["data"]["id"]
    for index in range(4):
        client.patch(
            f"{INCIDENTS}/{incident_id}", headers=_headers(), json={"title": f"Title {index}"}
        )

    first = _timeline(client, incident_id, "?limit=3").json()
    second = _timeline(client, incident_id, f"?limit=3&cursor={first['meta']['next_cursor']}")

    titles = [event["after"]["title"] for event in first["data"] + second.json()["data"]]
    assert titles == ["Paged", "Title 0", "Title 1", "Title 2", "Title 3"]
    assert second.json()["meta"]["next_cursor"] is None


def test_timeline_follows_incident_visibility(client: TestClient, database_url: str) -> None:
    incident_id = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Private", "severity": "sev3"}
    ).json()["data"]["id"]

    other_workspace = client.get(
        f"{INCIDENTS}/{incident_id}/timeline", headers=_headers(WORKSPACE_A1)
    )
    unknown = _timeline(client, str(uuid.uuid4()))

    assert other_workspace.json()["code"] == "INCIDENT_NOT_FOUND"
    assert unknown.json()["code"] == "INCIDENT_NOT_FOUND"

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(IncidentTimelineEvent.id))).all())

    assert run_as_probe_role(database_url, visible) == 0


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE incident_timeline_events SET kind = 'tampered'",
        "DELETE FROM incident_timeline_events",
    ],
)
def test_timeline_events_are_append_only(
    client: TestClient, database_url: str, statement: str
) -> None:
    client.post(INCIDENTS, headers=_headers(), json={"title": "Immutable", "severity": "sev4"})

    async def mutate(session: AsyncSession) -> None:
        await session.execute(text(statement))

    with pytest.raises(DBAPIError, match="append-only"):
        run_as_superuser(database_url, mutate)


def test_invalid_cursor_is_rejected(client: TestClient) -> None:
    incident_id = client.post(
        INCIDENTS, headers=_headers(), json={"title": "Cursor", "severity": "sev4"}
    ).json()["data"]["id"]
    task_cursor = "eyJ2IjoxLCJwIjpbIm5vdC1hLW51bWJlciJdfQ"

    response = _timeline(client, incident_id, f"?cursor={task_cursor}")

    assert (response.status_code, response.json()["code"]) == (422, "INVALID_CURSOR")
