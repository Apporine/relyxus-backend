"""Configuration versions (MPS-14A.07, MPS-20.29, MPS-8A.06)."""

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
from relyxus_api.modules.configuration.model import ConfigurationVersion
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    BOB,
    ORG_A,
    WORKSPACE_A1,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration


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


def _headers(subject: str = "sub-bob", workspace: uuid.UUID = WORKSPACE_B1) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
    }


def _versions(client: TestClient, object_type: str, object_id: str, query: str = "") -> Any:
    return client.get(
        f"/api/v1/configuration/{object_type}/{object_id}/versions{query}",
        headers=_headers("sub-amira"),
    ).json()


def test_team_changes_are_versioned(client: TestClient) -> None:
    team_id = client.post(
        "/api/v1/teams", headers=_headers(), json={"key": "versioned", "name": "Before"}
    ).json()["data"]["id"]
    client.patch(f"/api/v1/teams/{team_id}", headers=_headers(), json={"name": "After"})

    versions = _versions(client, "team", team_id)["data"]

    assert [version["version"] for version in versions] == [1, 2]
    assert versions[0]["difference"]["name"] == {"before": None, "after": "Before"}
    assert versions[1]["difference"] == {"name": {"before": "Before", "after": "After"}}
    assert versions[1]["snapshot"]["name"] == "After"
    assert (versions[1]["source"], versions[1]["actor_user_id"]) == ("api", str(BOB))


def test_service_changes_are_versioned_and_readable_one_by_one(client: TestClient) -> None:
    service_id = client.post(
        "/api/v1/services",
        headers=_headers(),
        json={"key": "ledger", "name": "Ledger", "tier": "tier_2", "environment": "production"},
    ).json()["data"]["id"]
    client.patch(f"/api/v1/services/{service_id}", headers=_headers(), json={"is_archived": True})

    second = client.get(
        f"/api/v1/configuration/service/{service_id}/versions/2", headers=_headers()
    ).json()["data"]
    missing = client.get(
        f"/api/v1/configuration/service/{service_id}/versions/3", headers=_headers()
    )

    assert second["difference"] == {"is_archived": {"before": False, "after": True}}
    assert missing.json()["code"] == "CONFIGURATION_VERSION_NOT_FOUND"


def test_versions_page_and_stay_in_their_workspace(client: TestClient) -> None:
    team_id = client.post(
        "/api/v1/teams", headers=_headers(), json={"key": "paged", "name": "Name 0"}
    ).json()["data"]["id"]
    for index in range(1, 4):
        client.patch(f"/api/v1/teams/{team_id}", headers=_headers(), json={"name": f"Name {index}"})

    first = _versions(client, "team", team_id, "?limit=3")
    second = _versions(client, "team", team_id, f"?limit=3&cursor={first['meta']['next_cursor']}")
    foreign = client.get(
        f"/api/v1/configuration/team/{team_id}/versions",
        headers=_headers("sub-amira", WORKSPACE_A1),
    ).json()["data"]

    assert [v["version"] for v in first["data"] + second["data"]] == [1, 2, 3, 4]
    assert foreign == []


@pytest.mark.parametrize(
    "statement",
    ["UPDATE configuration_versions SET version = 99", "DELETE FROM configuration_versions"],
)
def test_versions_are_append_only(client: TestClient, database_url: str, statement: str) -> None:
    client.post(
        "/api/v1/teams",
        headers=_headers(),
        json={"key": f"t-{uuid.uuid4().hex[:6]}", "name": "Immutable"},
    )

    async def mutate(session: AsyncSession) -> None:
        await session.execute(text(statement))

    with pytest.raises(DBAPIError, match="append-only"):
        run_as_superuser(database_url, mutate)


def test_versions_are_tenant_isolated(client: TestClient, database_url: str) -> None:
    client.post(
        "/api/v1/teams",
        headers=_headers(),
        json={"key": f"t-{uuid.uuid4().hex[:6]}", "name": "Isolated"},
    )

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(ConfigurationVersion.id))).all())

    assert run_as_probe_role(database_url, visible) == 0


def test_unknown_object_type_is_rejected(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/configuration/policy/{uuid.uuid4()}/versions", headers=_headers()
    )

    assert response.status_code == 422
