"""The service catalogue (MPS-14.01, MPS-20.08)."""

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
from relyxus_api.modules.catalog.model import CatalogService
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
SERVICES = "/api/v1/services"


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


def _headers(
    subject: str = "sub-bob", workspace: uuid.UUID = WORKSPACE_B1, key: str | None = None
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": key or f"idem-{uuid.uuid4()}",
    }


def _team(client: TestClient) -> str:
    team_id: str = client.post(
        "/api/v1/teams",
        headers=_headers(),
        json={"key": f"team-{uuid.uuid4().hex[:8]}", "name": "Owners"},
    ).json()["data"]["id"]
    return team_id


def _create(client: TestClient, **body: Any) -> Any:
    payload = {
        "key": f"svc-{uuid.uuid4().hex[:8]}",
        "name": "Card gateway",
        "tier": "tier_1",
        "environment": "production",
        **body,
    }
    return client.post(SERVICES, headers=_headers(), json=payload)


def test_create_and_read_a_service(client: TestClient) -> None:
    team_id = _team(client)

    created = _create(
        client, key="card-gateway", owner_team_id=team_id, labels={"region": "eu-west-1"}
    )

    data = created.json()["data"]
    assert created.status_code == 201
    assert (data["key"], data["tier"], data["environment"], data["owner_team_id"]) == (
        "card-gateway",
        "tier_1",
        "production",
        team_id,
    )
    assert data["labels"] == {"region": "eu-west-1"}
    fetched = client.get(f"{SERVICES}/{data['id']}", headers=_headers("sub-amira"))
    assert fetched.json()["data"] == data


@pytest.mark.parametrize(
    "body",
    [
        {"key": "Card Gateway"},
        {"tier": "critical"},
        {"environment": "Production"},
        {"labels": {"Bad Key": "x"}},
        {"labels": {"k": "v" * 201}},
        {"labels": {f"k{index}": "v" for index in range(51)}},
    ],
)
def test_invalid_services_are_rejected(client: TestClient, body: dict[str, Any]) -> None:
    assert _create(client, **body).status_code == 422


def test_key_unique_and_owner_team_in_workspace(client: TestClient) -> None:
    _create(client, key="ledger")
    other_team = client.post(
        "/api/v1/teams",
        headers=_headers("sub-amira", WORKSPACE_A1),
        json={"key": "other-team", "name": "Other"},
    )

    duplicate = _create(client, key="ledger")
    foreign_team = _create(client, owner_team_id=str(uuid.uuid4()))

    assert other_team.status_code == 403
    assert (duplicate.status_code, duplicate.json()["code"]) == (409, "SERVICE_KEY_TAKEN")
    assert foreign_team.json()["code"] == "SERVICE_OWNER_TEAM_NOT_FOUND"


def test_only_owners_and_admins_change_services(client: TestClient) -> None:
    service_id = _create(client).json()["data"]["id"]

    create = client.post(
        SERVICES,
        headers=_headers("sub-amira"),
        json={"key": "nope", "name": "Nope", "tier": "tier_4", "environment": "dev"},
    )
    update = client.patch(
        f"{SERVICES}/{service_id}", headers=_headers("sub-amira"), json={"name": "x"}
    )

    for response in (create, update):
        assert (response.status_code, response.json()["code"]) == (
            403,
            "INSUFFICIENT_WORKSPACE_ROLE",
        )


def test_update_clear_and_archive(client: TestClient) -> None:
    team_id = _team(client)
    created = _create(client, owner_team_id=team_id, labels={"a": "1"})
    service_id, etag = created.json()["data"]["id"], created.headers["etag"]

    updated = client.patch(
        f"{SERVICES}/{service_id}",
        headers={**_headers(), "If-Match": etag},
        json={"tier": "tier_2", "owner_team_id": None, "labels": {"b": "2"}},
    ).json()["data"]
    stale = client.patch(
        f"{SERVICES}/{service_id}", headers={**_headers(), "If-Match": etag}, json={"name": "x"}
    )
    archived = client.patch(
        f"{SERVICES}/{service_id}", headers=_headers(), json={"is_archived": True}
    ).json()["data"]
    no_op = client.patch(f"{SERVICES}/{service_id}", headers=_headers(), json={"is_archived": True})

    assert (updated["tier"], updated["owner_team_id"], updated["labels"]) == (
        "tier_2",
        None,
        {"b": "2"},
    )
    assert stale.status_code == 412
    assert archived["archived_at"] is not None
    assert no_op.json()["code"] == "SERVICE_NO_CHANGES"


def test_list_filters_and_hides_archived(client: TestClient) -> None:
    team_id = _team(client)
    tier_3 = _create(client, owner_team_id=team_id, tier="tier_3").json()["data"]["id"]
    tier_4 = _create(client, owner_team_id=team_id, tier="tier_4").json()["data"]["id"]
    archived = _create(client, owner_team_id=team_id, tier="tier_4").json()["data"]["id"]
    client.patch(f"{SERVICES}/{archived}", headers=_headers(), json={"is_archived": True})

    def ids(query: str) -> list[str]:
        return [
            item["id"]
            for item in client.get(f"{SERVICES}?{query}", headers=_headers()).json()["data"]
        ]

    assert ids(f"owner_team_id={team_id}") == [tier_3, tier_4]
    assert ids(f"owner_team_id={team_id}&tier=tier_4") == [tier_4]
    assert ids(f"owner_team_id={team_id}&include_archived=true") == [tier_3, tier_4, archived]


def test_services_are_tenant_isolated(client: TestClient, database_url: str) -> None:
    service_id = _create(client).json()["data"]["id"]

    other = client.get(f"{SERVICES}/{service_id}", headers=_headers("sub-amira", WORKSPACE_A1))

    assert other.json()["code"] == "SERVICE_NOT_FOUND"

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(CatalogService.id))).all())

    assert run_as_probe_role(database_url, visible) == 0
