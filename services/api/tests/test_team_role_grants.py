"""Team role grants: members inherit their teams' workspace roles (Q-18, Q-40)."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
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
from relyxus_api.modules.access.repository import USER_SETTING
from relyxus_api.modules.team.model import TeamMember, TeamRoleGrant
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from relyxus_api.shared.db.transaction_settings import set_transaction_settings
from tenancy_fixtures import (
    AMIRA,
    ISSUER,
    ORG_B,
    WORKSPACE_A1,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration
TEAMS = "/api/v1/teams"
AUDIT_EVENTS = "/api/v1/audit-events"
CURRENT_WORKSPACE = "/api/v1/workspaces/current"
CAROL = uuid.uuid4()
DAN = uuid.uuid4()


async def _seed_owner_and_member(session: AsyncSession) -> None:
    for user_id, subject in ((CAROL, "sub-carol"), (DAN, "sub-dan")):
        session.add(
            User(
                id=user_id,
                idp_issuer=ISSUER,
                idp_subject=subject,
                email=None,
                display_name=None,
                status="active",
            )
        )
    await session.flush()
    for user_id, role in ((CAROL, "owner"), (DAN, "viewer")):
        session.add(
            WorkspaceMembership(
                organization_id=ORG_B, workspace_id=WORKSPACE_B1, user_id=user_id, role=role
            )
        )


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)
    run_as_superuser(url, seed_two_organisations_with_members)
    run_as_superuser(url, _seed_owner_and_member)
    return url


class _SubjectTokenVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_app(make_settings(database_url=database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    return TestClient(app)


def _headers(subject: str = "sub-carol", workspace: uuid.UUID = WORKSPACE_B1) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": f"idem-{uuid.uuid4()}",
    }


def _team_with(client: TestClient, member: uuid.UUID) -> str:
    team_id: str = client.post(
        TEAMS,
        headers=_headers(),
        json={"key": f"team-{uuid.uuid4().hex[:8]}", "name": "Auditors"},
    ).json()["data"]["id"]
    client.put(f"{TEAMS}/{team_id}/members/{member}", headers=_headers())
    return team_id


def _roles(client: TestClient, subject: str) -> list[str]:
    response: Any = client.get(CURRENT_WORKSPACE, headers=_headers(subject))
    roles: list[str] = response.json()["data"]["roles"]
    return roles


def test_members_inherit_and_lose_team_roles(client: TestClient) -> None:
    team_id = _team_with(client, DAN)
    assert client.get(AUDIT_EVENTS, headers=_headers("sub-dan")).status_code == 403

    granted = client.put(f"{TEAMS}/{team_id}/roles/auditor", headers=_headers())

    assert granted.json()["data"]["role"] == "auditor"
    assert _roles(client, "sub-dan") == ["auditor", "viewer"]
    assert client.get(AUDIT_EVENTS, headers=_headers("sub-dan")).status_code == 200

    revoked = client.delete(f"{TEAMS}/{team_id}/roles/auditor", headers=_headers())

    assert revoked.status_code == 204
    assert _roles(client, "sub-dan") == ["viewer"]
    assert client.get(AUDIT_EVENTS, headers=_headers("sub-dan")).status_code == 403


def test_leaving_the_team_drops_the_role(client: TestClient) -> None:
    team_id = _team_with(client, DAN)
    client.put(f"{TEAMS}/{team_id}/roles/responder", headers=_headers())
    assert "responder" in _roles(client, "sub-dan")

    client.delete(f"{TEAMS}/{team_id}/members/{DAN}", headers=_headers())

    assert _roles(client, "sub-dan") == ["viewer"]


def test_team_roles_need_direct_workspace_membership(client: TestClient, database_url: str) -> None:
    team_id = _team_with(client, AMIRA)
    client.put(f"{TEAMS}/{team_id}/roles/admin", headers=_headers())
    assert "admin" in _roles(client, "sub-amira")

    async def drop_amira(session: AsyncSession) -> None:
        await session.execute(
            delete(WorkspaceMembership).where(
                WorkspaceMembership.user_id == AMIRA,
                WorkspaceMembership.workspace_id == WORKSPACE_B1,
            )
        )

    run_as_superuser(database_url, drop_amira)

    response = client.get(CURRENT_WORKSPACE, headers=_headers("sub-amira"))
    assert (response.status_code, response.json()["code"]) == (403, "WORKSPACE_ACCESS_DENIED")


def test_team_roles_do_not_cross_workspaces(client: TestClient) -> None:
    other = client.get(CURRENT_WORKSPACE, headers=_headers("sub-amira", WORKSPACE_A1))

    assert sorted(other.json()["data"]["roles"]) == ["responder", "viewer"]


def test_only_owners_grant_and_grants_are_idempotent(client: TestClient) -> None:
    team_id = _team_with(client, DAN)

    by_admin = client.put(f"{TEAMS}/{team_id}/roles/owner", headers=_headers("sub-bob"))
    first = client.put(f"{TEAMS}/{team_id}/roles/viewer", headers=_headers())
    again = client.put(f"{TEAMS}/{team_id}/roles/viewer", headers=_headers())
    listed = client.get(f"{TEAMS}/{team_id}/roles", headers=_headers("sub-dan")).json()["data"]
    missing = client.delete(f"{TEAMS}/{team_id}/roles/auditor", headers=_headers())
    unknown_role = client.put(f"{TEAMS}/{team_id}/roles/superuser", headers=_headers())

    assert (by_admin.status_code, by_admin.json()["code"]) == (403, "INSUFFICIENT_WORKSPACE_ROLE")
    assert again.json() == first.json()
    assert [grant["role"] for grant in listed] == ["viewer"]
    assert missing.json()["code"] == "TEAM_ROLE_GRANT_NOT_FOUND"
    assert unknown_role.status_code == 422


def test_user_context_reveals_only_own_teams_and_grants(
    client: TestClient, database_url: str
) -> None:
    own_team = _team_with(client, DAN)
    other_team = _team_with(client, CAROL)
    for team_id in (own_team, other_team):
        client.put(f"{TEAMS}/{team_id}/roles/responder", headers=_headers())

    async def visible_to_dan(session: AsyncSession) -> tuple[set[str], set[str]]:
        await set_transaction_settings(session, {USER_SETTING: str(DAN)})
        members = await session.scalars(select(TeamMember.team_id))
        grants = await session.scalars(select(TeamRoleGrant.team_id))
        return {str(team) for team in members}, {str(team) for team in grants}

    member_teams, grant_teams = run_as_probe_role(database_url, visible_to_dan)

    assert own_team in member_teams
    assert other_team not in member_teams
    assert own_team in grant_teams
    assert other_team not in grant_teams
