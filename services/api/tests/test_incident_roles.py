"""Incident role assignments (MPS-11.04, MPS-14.06)."""

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
from relyxus_api.modules.incident.role_model import IncidentRoleAssignment
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    AMIRA,
    BOB,
    ORG_A,
    SUSPENDED,
    WORKSPACE_A1,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
INCIDENTS = "/api/v1/incidents"
COMMANDER = ("sub-amira", WORKSPACE_B1)
RESPONDER = ("sub-amira", WORKSPACE_A1)
ADMIN = ("sub-bob", WORKSPACE_B1)


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


def _headers(actor: tuple[str, uuid.UUID]) -> dict[str, str]:
    subject, workspace = actor
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
    }


def _declare(client: TestClient, actor: tuple[str, uuid.UUID] = COMMANDER) -> str:
    response = client.post(
        INCIDENTS, headers=_headers(actor), json={"title": "Roles test", "severity": "sev2"}
    )
    incident_id: str = response.json()["data"]["id"]
    return incident_id


def _assign(
    client: TestClient,
    incident_id: str,
    role: str,
    user_id: uuid.UUID,
    actor: tuple[str, uuid.UUID] = COMMANDER,
) -> Any:
    return client.put(
        f"{INCIDENTS}/{incident_id}/roles/{role}",
        headers=_headers(actor),
        json={"user_id": str(user_id)},
    )


def test_commander_assigns_replaces_and_lists_roles(client: TestClient, database_url: str) -> None:
    incident_id = _declare(client)

    assert _assign(client, incident_id, "incident_commander", AMIRA).status_code == 200
    assert _assign(client, incident_id, "scribe", BOB).status_code == 200
    replaced = _assign(client, incident_id, "incident_commander", BOB).json()["data"]
    assert replaced["user_id"] == str(BOB)

    listed = client.get(f"{INCIDENTS}/{incident_id}/roles", headers=_headers(ADMIN)).json()["data"]
    assert {(item["role"], item["user_id"]) for item in listed} == {
        ("incident_commander", str(BOB)),
        ("scribe", str(BOB)),
    }

    async def audit(session: AsyncSession) -> list[AuditEvent]:
        rows = await session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.target_id == incident_id, AuditEvent.action == "incident.role_assigned"
            )
            .order_by(AuditEvent.sequence)
        )
        return list(rows)

    events = run_as_superuser(database_url, audit)
    assert len(events) == 3
    assert events[-1].before_state == {"role": "incident_commander", "user_id": str(AMIRA)}
    assert events[-1].after_state == {"role": "incident_commander", "user_id": str(BOB)}


def test_reassigning_the_same_holder_changes_nothing(client: TestClient) -> None:
    incident_id = _declare(client)
    first = _assign(client, incident_id, "scribe", BOB).json()["data"]

    again = _assign(client, incident_id, "scribe", BOB).json()["data"]

    assert again == first


def test_assignee_must_be_a_workspace_member(client: TestClient) -> None:
    incident_id = _declare(client)

    for outsider in (SUSPENDED, uuid.uuid4()):
        response = _assign(client, incident_id, "scribe", outsider)
        assert (response.status_code, response.json()["code"]) == (
            422,
            "INCIDENT_ROLE_ASSIGNEE_NOT_MEMBER",
        )


def test_only_commanders_and_owners_assign(client: TestClient) -> None:
    responder_incident = _declare(client, RESPONDER)
    admin_target = _declare(client)

    assert _assign(client, responder_incident, "scribe", AMIRA, RESPONDER).status_code == 403
    assert _assign(client, admin_target, "scribe", BOB, ADMIN).status_code == 403


def test_unassign_is_idempotent(client: TestClient) -> None:
    incident_id = _declare(client)
    _assign(client, incident_id, "communications_lead", BOB)
    path = f"{INCIDENTS}/{incident_id}/roles/communications_lead"

    assert client.delete(path, headers=_headers(COMMANDER)).status_code == 204
    assert client.delete(path, headers=_headers(COMMANDER)).status_code == 204
    assert (
        client.get(f"{INCIDENTS}/{incident_id}/roles", headers=_headers(COMMANDER)).json()["data"]
        == []
    )


def test_terminal_incident_roles_are_frozen(client: TestClient) -> None:
    incident_id = _declare(client)
    client.post(
        f"{INCIDENTS}/{incident_id}/transitions",
        headers=_headers(COMMANDER),
        json={"target_state": "cancelled", "reason": "dup"},
    )

    response = _assign(client, incident_id, "scribe", BOB)

    assert (response.status_code, response.json()["code"]) == (409, "INCIDENT_NOT_EDITABLE")


@pytest.mark.parametrize("role", ["owner", "payments_on_call", "INCIDENT_COMMANDER"])
def test_unknown_incident_roles_are_rejected(client: TestClient, role: str) -> None:
    assert _assign(client, _declare(client), role, BOB).status_code == 422


def test_rls_hides_other_organisations_assignments(client: TestClient, database_url: str) -> None:
    incident_id = _declare(client)
    _assign(client, incident_id, "scribe", BOB)

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        rows = await session.scalars(select(IncidentRoleAssignment.id))
        return len(rows.all())

    assert run_as_probe_role(database_url, visible) == 0
