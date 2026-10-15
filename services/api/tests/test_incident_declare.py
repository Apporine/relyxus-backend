"""Declare / draft and read incidents (MPS-8A.08, MPS-8A.20, MPS-8A.22, MPS-22A.05)."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
from relyxus_api.modules.access.model import User, WorkspaceMembership
from relyxus_api.modules.audit.model import AuditEvent
from relyxus_api.modules.audit.service import verify_events
from relyxus_api.modules.incident.model import Incident
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    AMIRA,
    ISSUER,
    ORG_A,
    ORG_B,
    WORKSPACE_A1,
    WORKSPACE_A2,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
INCIDENTS = "/api/v1/incidents"
SIBLING_INCIDENT = uuid.uuid4()
FOREIGN_INCIDENT = uuid.uuid4()


async def _seed(session: AsyncSession) -> None:
    await seed_two_organisations_with_members(session)
    viewer_id = uuid.uuid4()
    session.add(
        User(
            id=viewer_id,
            idp_issuer=ISSUER,
            idp_subject="sub-viola",
            email=None,
            display_name=None,
            status="active",
        )
    )
    await session.flush()
    session.add(
        WorkspaceMembership(
            organization_id=ORG_A, workspace_id=WORKSPACE_A1, user_id=viewer_id, role="viewer"
        )
    )
    for incident_id, org_id, workspace_id in (
        (SIBLING_INCIDENT, ORG_A, WORKSPACE_A2),
        (FOREIGN_INCIDENT, ORG_B, WORKSPACE_B1),
    ):
        session.add(
            Incident(
                id=incident_id,
                organization_id=org_id,
                workspace_id=workspace_id,
                number=1,
                lifecycle_state="triage",
                severity="sev3",
                title="seeded",
            )
        )


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)
    run_as_superuser(url, _seed)
    return url


class _SubjectTokenVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_app(make_settings(database_url=database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    return TestClient(app)


def _headers(
    subject: str = "sub-amira", key: str | None = None, workspace: uuid.UUID = WORKSPACE_A1
) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {subject}", WORKSPACE_HEADER: str(workspace)}
    headers["Idempotency-Key"] = key or f"idem-{uuid.uuid4()}"
    return headers


def _declare(client: TestClient, body: dict[str, Any], **header_args: Any) -> Any:
    return client.post(INCIDENTS, headers=_headers(**header_args), json=body)


def test_declare_moves_to_investigating_and_records_declaration(client: TestClient) -> None:
    before = datetime.now(UTC)
    response = _declare(client, {"title": "  Card authorisations failing  ", "severity": "sev1"})

    data = response.json()["data"]
    assert response.status_code == 201
    assert data["lifecycle_state"] == "investigating"
    assert data["title"] == "Card authorisations failing"
    assert data["declared_by_user_id"] == str(AMIRA)
    assert datetime.fromisoformat(data["declared_at"]) >= before
    assert response.headers["location"] == f"{INCIDENTS}/{data['id']}"
    assert client.get(response.headers["location"], headers=_headers()).json()["data"] == data


def test_draft_stays_in_triage_without_declaration(client: TestClient) -> None:
    data = _declare(
        client, {"title": "Possible DNS issue", "severity": "sev3", "is_declared": False}
    ).json()["data"]

    assert data["lifecycle_state"] == "triage"
    assert data["declared_at"] is None
    assert data["declared_by_user_id"] is None


def test_declaration_is_audited_in_the_same_chain(client: TestClient, database_url: str) -> None:
    incident_id = _declare(client, {"title": "Payments latency", "severity": "sev2"}).json()[
        "data"
    ]["id"]

    async def read_chain(session: AsyncSession) -> tuple[AuditEvent, list[AuditEvent]]:
        event = await session.scalar(select(AuditEvent).where(AuditEvent.target_id == incident_id))
        assert event is not None
        chain = list(
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.chain_id == WORKSPACE_A1)
                .order_by(AuditEvent.sequence)
            )
        )
        return event, chain

    event, chain = run_as_superuser(database_url, read_chain)
    assert (event.action, event.target_type, event.actor_user_id) == (
        "incident.declared",
        "incident",
        AMIRA,
    )
    assert event.after_state is not None
    assert event.after_state["detected_at"] is not None
    assert event.after_state == {
        "lifecycle_state": "investigating",
        "severity": "sev2",
        "title": "Payments latency",
        "impact_started_at": None,
        "detected_at": event.after_state["detected_at"],
    }
    assert verify_events(chain) == []


def test_retry_with_same_key_replays_and_creates_nothing_new(client: TestClient) -> None:
    key = f"idem-{uuid.uuid4()}"
    body = {"title": "Replay me", "severity": "sev2"}

    first = _declare(client, body, key=key)
    second = _declare(client, body, key=key)

    assert second.status_code == 201
    assert second.json() == first.json()


def test_reusing_a_key_with_another_body_is_a_conflict(client: TestClient) -> None:
    key = f"idem-{uuid.uuid4()}"
    _declare(client, {"title": "First", "severity": "sev2"}, key=key)

    response = _declare(client, {"title": "Second", "severity": "sev2"}, key=key)

    assert (response.status_code, response.json()["code"]) == (409, "IDEMPOTENCY_KEY_REUSE")


def test_viewer_cannot_declare(client: TestClient) -> None:
    response = _declare(client, {"title": "x", "severity": "sev2"}, subject="sub-viola")

    assert (response.status_code, response.json()["code"]) == (403, "INSUFFICIENT_WORKSPACE_ROLE")


@pytest.mark.parametrize(
    "body",
    [
        {"title": "   ", "severity": "sev2"},
        {"title": "x" * 501, "severity": "sev2"},
        {"title": "x", "severity": "critical"},
        {"title": "x", "severity": "sev2", "lifecycle_state": "closed"},
        {"severity": "sev2"},
    ],
)
def test_invalid_bodies_are_rejected(client: TestClient, body: dict[str, Any]) -> None:
    response = _declare(client, body)

    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION_FAILED")


def test_idempotency_key_is_required(client: TestClient) -> None:
    headers = _headers()
    del headers["Idempotency-Key"]

    assert (
        client.post(INCIDENTS, headers=headers, json={"title": "x", "severity": "sev2"}).status_code
        == 422
    )


@pytest.mark.parametrize("incident_id", [SIBLING_INCIDENT, FOREIGN_INCIDENT, uuid.uuid4()])
def test_incidents_outside_the_open_workspace_are_not_found(
    client: TestClient, incident_id: uuid.UUID
) -> None:
    response = client.get(f"{INCIDENTS}/{incident_id}", headers=_headers())

    assert (response.status_code, response.json()["code"]) == (404, "INCIDENT_NOT_FOUND")


def test_database_rejects_declared_states_without_declaration_time(database_url: str) -> None:
    async def insert_undeclared(session: AsyncSession) -> None:
        session.add(
            Incident(
                organization_id=ORG_A,
                workspace_id=WORKSPACE_A1,
                number=9999,
                lifecycle_state="investigating",
                severity="sev2",
                title="x",
            )
        )
        await session.flush()

    with pytest.raises(IntegrityError):
        run_as_superuser(database_url, insert_undeclared)


def test_rls_hides_other_organisations_incidents(database_url: str) -> None:
    async def visible_ids(session: AsyncSession) -> set[uuid.UUID]:
        await apply_tenant_context(
            session, TenantContext(organization_id=ORG_A, workspace_id=WORKSPACE_A1)
        )
        return set((await session.scalars(select(Incident.id))).all())

    visible = run_as_probe_role(database_url, visible_ids)

    assert FOREIGN_INCIDENT not in visible
    assert SIBLING_INCIDENT in visible  # same organisation: the service adds the workspace filter
