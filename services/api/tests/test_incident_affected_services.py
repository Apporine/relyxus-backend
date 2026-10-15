"""Services affected by incidents (MPS-8A.08, MPS-15.02 filter by service)."""

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
from relyxus_api.modules.incident.affected_service_model import IncidentAffectedService
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
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


def _headers(subject: str = "sub-amira", workspace: uuid.UUID = WORKSPACE_B1) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
    }


def _service(client: TestClient, *, archived: bool = False) -> str:
    service_id: str = client.post(
        "/api/v1/services",
        headers=_headers("sub-bob"),
        json={
            "key": f"svc-{uuid.uuid4().hex[:8]}",
            "name": "Card gateway",
            "tier": "tier_1",
            "environment": "production",
        },
    ).json()["data"]["id"]
    if archived:
        client.patch(
            f"/api/v1/services/{service_id}",
            headers=_headers("sub-bob"),
            json={"is_archived": True},
        )
    return service_id


def _declare(client: TestClient, *service_ids: str) -> Any:
    return client.post(
        INCIDENTS,
        headers=_headers(),
        json={
            "title": "Payments down",
            "severity": "sev1",
            "affected_service_ids": list(service_ids),
        },
    )


def _services(client: TestClient, incident_id: str) -> list[str]:
    data = client.get(f"{INCIDENTS}/{incident_id}/services", headers=_headers()).json()["data"]
    return [item["service_id"] for item in data]


def test_declare_with_affected_services(client: TestClient, database_url: str) -> None:
    first, second = _service(client), _service(client)

    declared = _declare(client, first, second, first)

    incident_id = declared.json()["data"]["id"]
    assert declared.status_code == 201
    assert _services(client, incident_id) == [first, second]

    async def declared_state(session: AsyncSession) -> Any:
        return await session.scalar(
            select(AuditEvent.after_state).where(
                AuditEvent.target_id == incident_id, AuditEvent.action == "incident.declared"
            )
        )

    assert run_as_superuser(database_url, declared_state)["affected_service_ids"] == [
        first,
        second,
    ]


def test_declare_rejects_unknown_archived_and_foreign_services(client: TestClient) -> None:
    archived = _service(client, archived=True)

    for service_id in (archived, str(uuid.uuid4())):
        response = _declare(client, service_id)
        assert (response.status_code, response.json()["code"]) == (
            422,
            "INCIDENT_AFFECTED_SERVICE_INVALID",
        )
    assert _declare(client, *[str(uuid.uuid4()) for _ in range(51)]).status_code == 422


def test_add_and_remove_services_later(client: TestClient) -> None:
    incident_id = _declare(client).json()["data"]["id"]
    service_id = _service(client)
    path = f"{INCIDENTS}/{incident_id}/services/{service_id}"

    added = client.put(path, headers=_headers())
    again = client.put(path, headers=_headers())
    removed = client.delete(path, headers=_headers())
    missing = client.delete(path, headers=_headers())

    assert added.json()["data"]["service_id"] == service_id
    assert again.json() == added.json()
    assert removed.status_code == 204
    assert missing.json()["code"] == "INCIDENT_AFFECTED_SERVICE_NOT_FOUND"
    kinds = [
        event["kind"]
        for event in client.get(f"{INCIDENTS}/{incident_id}/timeline", headers=_headers()).json()[
            "data"
        ]
    ]
    assert kinds[-2:] == ["incident.service_added", "incident.service_removed"]


def test_frozen_incidents_keep_their_services(client: TestClient) -> None:
    service_id = _service(client)
    incident_id = _declare(client, service_id).json()["data"]["id"]
    client.post(
        f"{INCIDENTS}/{incident_id}/transitions",
        headers=_headers(),
        json={"target_state": "cancelled", "reason": "Duplicate"},
    )

    response = client.delete(f"{INCIDENTS}/{incident_id}/services/{service_id}", headers=_headers())

    assert (response.status_code, response.json()["code"]) == (409, "INCIDENT_NOT_EDITABLE")
    assert _services(client, incident_id) == [service_id]


def test_list_incidents_by_service(client: TestClient) -> None:
    gateway, ledger = _service(client), _service(client)
    on_gateway = _declare(client, gateway).json()["data"]["id"]
    on_both = _declare(client, gateway, ledger).json()["data"]["id"]
    _declare(client)

    def ids(query: str) -> list[str]:
        response = client.get(f"{INCIDENTS}?{query}", headers=_headers())
        return [item["id"] for item in response.json()["data"]]

    assert ids(f"service_id={gateway}") == [on_both, on_gateway]
    assert ids(f"service_id={ledger}") == [on_both]
    assert ids(f"service_id={ledger}&lifecycle_state=triage") == []


def test_links_are_tenant_isolated(client: TestClient, database_url: str) -> None:
    _declare(client, _service(client))
    foreign = client.get(
        f"{INCIDENTS}/{uuid.uuid4()}/services", headers=_headers(workspace=WORKSPACE_A1)
    )

    assert foreign.json()["code"] == "INCIDENT_NOT_FOUND"

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(IncidentAffectedService.id))).all())

    assert run_as_probe_role(database_url, visible) == 0
