"""Incident lifecycle transitions (MPS-8A.09-8A.17, MPS-8A.20, MPS-8A.22, MPS-22A.05)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.modules.audit.model import AuditEvent
from relyxus_api.modules.audit.service import verify_events
from relyxus_api.modules.incident.model import Incident
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    WORKSPACE_A1,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
INCIDENTS = "/api/v1/incidents"
COMMANDER = ("sub-amira", WORKSPACE_B1)  # incident_commander in B1
RESPONDER = ("sub-amira", WORKSPACE_A1)  # responder + viewer in A1
ADMIN = ("sub-bob", WORKSPACE_B1)  # admin in B1


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


def _headers(actor: tuple[str, uuid.UUID], **extra: str) -> dict[str, str]:
    subject, workspace = actor
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
        **extra,
    }


def _declare(
    client: TestClient, actor: tuple[str, uuid.UUID] = COMMANDER, *, is_declared: bool = True
) -> str:
    body = {"title": "Payments degraded", "severity": "sev2", "is_declared": is_declared}
    response = client.post(INCIDENTS, headers=_headers(actor), json=body)
    assert response.status_code == 201, response.text
    incident_id: str = response.json()["data"]["id"]
    return incident_id


def _move(
    client: TestClient,
    incident_id: str,
    target: str,
    actor: tuple[str, uuid.UUID] = COMMANDER,
    **body: Any,
) -> Any:
    return client.post(
        f"{INCIDENTS}/{incident_id}/transitions",
        headers=_headers(actor, **body.pop("headers", {})),
        json={"target_state": target, **body},
    )


def _error(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["code"]


def test_commander_walks_the_lifecycle_and_timestamps_are_recorded(client: TestClient) -> None:
    incident_id = _declare(client)
    for target in ("mitigating", "monitoring", "mitigating", "monitoring"):
        assert _move(client, incident_id, target).status_code == 200

    resolved = _move(client, incident_id, "resolved").json()["data"]
    assert resolved["mitigated_at"] is not None
    assert resolved["resolved_at"] is not None

    assert _error(_move(client, incident_id, "investigating")) == (
        422,
        "INCIDENT_TRANSITION_REASON_REQUIRED",
    )
    reopened = _move(
        client, incident_id, "investigating", reason="Errors returned after deploy"
    ).json()["data"]
    assert reopened["lifecycle_state"] == "investigating"
    assert reopened["resolved_at"] is None


def test_closing_waits_for_post_incident_review(client: TestClient) -> None:
    incident_id = _declare(client)
    for target in ("mitigating", "monitoring", "resolved"):
        _move(client, incident_id, target)

    assert _error(_move(client, incident_id, "closed")) == (409, "INCIDENT_REVIEW_REQUIRED")


def test_roles_are_enforced_per_transition(client: TestClient) -> None:
    incident_id = _declare(client, RESPONDER)

    assert _move(client, incident_id, "mitigating", RESPONDER).status_code == 200
    assert _error(_move(client, incident_id, "monitoring", RESPONDER)) == (
        403,
        "INSUFFICIENT_WORKSPACE_ROLE",
    )

    other = _declare(client)
    assert _error(_move(client, other, "cancelled", ADMIN, reason="dup")) == (
        403,
        "INSUFFICIENT_WORKSPACE_ROLE",
    )


def test_lifecycle_graph_and_repeats_are_rejected(client: TestClient) -> None:
    incident_id = _declare(client)

    assert _error(_move(client, incident_id, "resolved")) == (
        409,
        "INCIDENT_INVALID_LIFECYCLE_TRANSITION",
    )
    assert _error(_move(client, incident_id, "investigating")) == (409, "INCIDENT_ALREADY_IN_STATE")


def test_cancel_needs_a_reason_and_is_terminal(client: TestClient) -> None:
    incident_id = _declare(client)

    assert _error(_move(client, incident_id, "cancelled")) == (
        422,
        "INCIDENT_TRANSITION_REASON_REQUIRED",
    )
    cancelled = _move(client, incident_id, "cancelled", reason="False alarm").json()["data"]
    assert cancelled["cancelled_at"] is not None
    assert _error(_move(client, incident_id, "investigating", reason="x")) == (
        409,
        "INCIDENT_INVALID_LIFECYCLE_TRANSITION",
    )


def test_merge_requires_an_open_incident_in_the_same_workspace(client: TestClient) -> None:
    source, target = _declare(client), _declare(client)
    other_workspace = _declare(client, RESPONDER)
    finished = _declare(client)
    _move(client, finished, "cancelled", reason="dup")

    for merge_into in (None, source, other_workspace, finished, str(uuid.uuid4())):
        response = _move(client, source, "merged", merged_into_incident_id=merge_into)
        assert _error(response) == (422, "INCIDENT_INVALID_MERGE_TARGET"), merge_into

    merged = _move(client, source, "merged", merged_into_incident_id=target).json()["data"]
    assert (merged["lifecycle_state"], merged["merged_into_incident_id"]) == ("merged", target)
    assert _error(_move(client, target, "mitigating", merged_into_incident_id=source)) == (
        422,
        "INCIDENT_INVALID_MERGE_TARGET",
    )


def test_reopen_is_refused_after_the_window(client: TestClient, database_url: str) -> None:
    incident_id = _declare(client)
    for target in ("mitigating", "monitoring", "resolved"):
        _move(client, incident_id, target)

    async def age_resolution(session: AsyncSession) -> None:
        await session.execute(
            update(Incident)
            .where(Incident.id == uuid.UUID(incident_id))
            .values(resolved_at=datetime.now(UTC) - timedelta(days=8))
        )

    run_as_superuser(database_url, age_resolution)
    assert _error(_move(client, incident_id, "investigating", reason="Recurred")) == (
        409,
        "INCIDENT_REOPEN_WINDOW_EXPIRED",
    )


def test_draft_is_declared_through_a_transition(client: TestClient) -> None:
    incident_id = _declare(client, is_declared=False)

    declared = _move(client, incident_id, "investigating").json()["data"]

    assert declared["declared_at"] is not None


def test_stale_if_match_is_refused(client: TestClient) -> None:
    incident_id = _declare(client)
    etag = client.get(f"{INCIDENTS}/{incident_id}", headers=_headers(COMMANDER)).headers["etag"]
    assert _move(client, incident_id, "mitigating", headers={"If-Match": etag}).status_code == 200

    stale = _move(client, incident_id, "monitoring", headers={"If-Match": etag})

    assert _error(stale) == (412, "PRECONDITION_FAILED")


def test_transitions_are_audited_once_and_chain_verifies(
    client: TestClient, database_url: str
) -> None:
    incident_id = _declare(client)
    key = f"idem-{uuid.uuid4()}"
    headers = {**_headers(COMMANDER), "Idempotency-Key": key}
    first = client.post(
        f"{INCIDENTS}/{incident_id}/transitions",
        headers=headers,
        json={"target_state": "mitigating"},
    )
    replay = client.post(
        f"{INCIDENTS}/{incident_id}/transitions",
        headers=headers,
        json={"target_state": "mitigating"},
    )
    assert replay.json() == first.json()

    async def read(session: AsyncSession) -> tuple[list[AuditEvent], list[AuditEvent]]:
        mine = list(
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.target_id == incident_id)
                .order_by(AuditEvent.sequence)
            )
        )
        chain = list(
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.chain_id == WORKSPACE_B1)
                .order_by(AuditEvent.sequence)
            )
        )
        return mine, chain

    mine, chain = run_as_superuser(database_url, read)
    assert [event.action for event in mine] == ["incident.declared", "incident.transitioned"]
    assert (mine[1].before_state, mine[1].after_state) == (
        {"lifecycle_state": "investigating"},
        {"lifecycle_state": "mitigating"},
    )
    assert verify_events(chain) == []
