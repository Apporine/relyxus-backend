"""Teams and team membership (MPS-14.01, MPS-14.02, MPS-20.05)."""

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
from relyxus_api.modules.team.model import Team
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
TEAMS = "/api/v1/teams"


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


def _create(client: TestClient, key: str | None = None, **body: Any) -> Any:
    payload = {"key": key or f"team-{uuid.uuid4().hex[:8]}", "name": "Payments SRE", **body}
    return client.post(TEAMS, headers=_headers(), json=payload)


def test_admin_creates_and_reads_a_team(client: TestClient, database_url: str) -> None:
    created = _create(client, "payments-sre", description="Card rails")

    data = created.json()["data"]
    assert created.status_code == 201
    assert created.headers["location"].endswith(data["id"])
    assert (data["key"], data["name"], data["description"]) == (
        "payments-sre",
        "Payments SRE",
        "Card rails",
    )
    fetched = client.get(f"{TEAMS}/{data['id']}", headers=_headers("sub-amira"))
    assert fetched.json()["data"] == data

    async def audited(session: AsyncSession) -> list[str]:
        rows = await session.scalars(
            select(AuditEvent.action).where(AuditEvent.target_id == data["id"])
        )
        return list(rows)

    assert run_as_superuser(database_url, audited) == ["team.created"]


def test_keys_are_unique_and_validated(client: TestClient) -> None:
    _create(client, "core-platform")

    duplicate = _create(client, "core-platform")
    invalid = _create(client, "Core Platform")

    assert (duplicate.status_code, duplicate.json()["code"]) == (409, "TEAM_KEY_TAKEN")
    assert invalid.status_code == 422


def test_only_owners_and_admins_change_teams(client: TestClient) -> None:
    team_id = _create(client).json()["data"]["id"]

    create = client.post(
        TEAMS, headers=_headers("sub-amira"), json={"key": "nope-team", "name": "Nope"}
    )
    rename = client.patch(
        f"{TEAMS}/{team_id}", headers=_headers("sub-amira"), json={"name": "Renamed"}
    )
    member = client.put(f"{TEAMS}/{team_id}/members/{AMIRA}", headers=_headers("sub-amira"))

    for response in (create, rename, member):
        assert (response.status_code, response.json()["code"]) == (
            403,
            "INSUFFICIENT_WORKSPACE_ROLE",
        )


def test_update_name_and_clear_description(client: TestClient) -> None:
    created = _create(client, description="Old")
    team_id, etag = created.json()["data"]["id"], created.headers["etag"]

    renamed = client.patch(
        f"{TEAMS}/{team_id}",
        headers={**_headers(), "If-Match": etag},
        json={"name": "Cards SRE", "description": None},
    )
    stale = client.patch(
        f"{TEAMS}/{team_id}", headers={**_headers(), "If-Match": etag}, json={"name": "Again"}
    )
    no_op = client.patch(f"{TEAMS}/{team_id}", headers=_headers(), json={"name": "Cards SRE"})
    key_change = client.patch(f"{TEAMS}/{team_id}", headers=_headers(), json={"key": "new"})

    assert (renamed.json()["data"]["name"], renamed.json()["data"]["description"]) == (
        "Cards SRE",
        None,
    )
    assert stale.status_code == 412
    assert no_op.json()["code"] == "TEAM_NO_CHANGES"
    assert key_change.status_code == 422


def test_membership(client: TestClient) -> None:
    team_id = _create(client).json()["data"]["id"]
    members = f"{TEAMS}/{team_id}/members"

    added = client.put(f"{members}/{AMIRA}", headers=_headers())
    again = client.put(f"{members}/{AMIRA}", headers=_headers())
    outsider = client.put(f"{members}/{SUSPENDED}", headers=_headers())
    client.put(f"{members}/{BOB}", headers=_headers())
    listed = client.get(members, headers=_headers()).json()["data"]
    removed = client.delete(f"{members}/{AMIRA}", headers=_headers())
    missing = client.delete(f"{members}/{AMIRA}", headers=_headers())

    assert added.json()["data"]["user_id"] == str(AMIRA)
    assert again.json() == added.json()
    assert outsider.json()["code"] == "TEAM_MEMBER_NOT_WORKSPACE_MEMBER"
    assert [member["user_id"] for member in listed] == [str(AMIRA), str(BOB)]
    assert removed.status_code == 204
    assert missing.json()["code"] == "TEAM_MEMBER_NOT_FOUND"


def test_teams_stay_in_their_workspace(client: TestClient, database_url: str) -> None:
    team_id = _create(client).json()["data"]["id"]

    other_workspace = client.get(f"{TEAMS}/{team_id}", headers=_headers("sub-amira", WORKSPACE_A1))
    listed = client.get(TEAMS, headers=_headers("sub-amira", WORKSPACE_A1)).json()["data"]

    assert other_workspace.json()["code"] == "TEAM_NOT_FOUND"
    assert listed == []

    async def visible(session: AsyncSession) -> int:
        await apply_tenant_context(session, TenantContext(organization_id=ORG_A))
        return len((await session.scalars(select(Team.id))).all())

    assert run_as_probe_role(database_url, visible) == 0


def test_list_pages_and_create_replays(client: TestClient) -> None:
    key = f"idem-{uuid.uuid4()}"
    body = {"key": "replayed-team", "name": "Replayed"}
    first = client.post(TEAMS, headers=_headers(key=key), json=body)
    retry = client.post(TEAMS, headers=_headers(key=key), json=body)

    page = client.get(f"{TEAMS}?limit=2", headers=_headers()).json()
    rest = client.get(
        f"{TEAMS}?limit=100&cursor={page['meta']['next_cursor']}", headers=_headers()
    ).json()

    assert retry.json() == first.json()
    ids = [team["id"] for team in page["data"] + rest["data"]]
    assert len(ids) == len(set(ids))
    assert first.json()["data"]["id"] in ids
