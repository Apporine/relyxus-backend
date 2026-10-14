"""Workspace picker and current workspace (MPS-15.02), plus the member-visibility policy."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
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
from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.tenancy.model import Organization, Workspace
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    AMIRA,
    BOB,
    ORG_A,
    ORG_B,
    WORKSPACE_A1,
    WORKSPACE_A2,
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


def _visible_as_user(url: str, user_id: uuid.UUID) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
    async def read(session: AsyncSession) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
        await AccessRepository().apply_user_context(session, user_id)
        workspaces = set((await session.scalars(select(Workspace.id))).all())
        organizations = set((await session.scalars(select(Organization.id))).all())
        return workspaces, organizations

    return run_as_probe_role(url, read)


def test_user_context_reveals_only_member_workspaces_and_organisations(database_url: str) -> None:
    assert _visible_as_user(database_url, AMIRA) == ({WORKSPACE_A1, WORKSPACE_B1}, {ORG_A, ORG_B})
    assert _visible_as_user(database_url, BOB) == ({WORKSPACE_B1}, {ORG_B})


def test_user_context_alone_cannot_write_workspaces(database_url: str) -> None:
    async def insert_workspace(session: AsyncSession) -> None:
        await AccessRepository().apply_user_context(session, AMIRA)
        session.add(
            Workspace(
                organization_id=ORG_A, key="sneaky", name="x", data_residency_region="eu-west-2"
            )
        )
        await session.flush()

    with pytest.raises(DBAPIError, match="row-level security"):
        run_as_probe_role(database_url, insert_workspace)


class _SubjectTokenVerifier:
    """Test double: the bearer token is the subject itself."""

    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_app(make_settings(database_url=database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    return TestClient(app)


def _auth(subject: str, workspace: uuid.UUID | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {subject}"}
    if workspace is not None:
        headers[WORKSPACE_HEADER] = str(workspace)
    return headers


def test_picker_lists_workspaces_across_organisations_with_roles(client: TestClient) -> None:
    body = client.get("/api/v1/me/workspaces", headers=_auth("sub-amira")).json()

    by_workspace = {item["workspace_id"]: item for item in body["data"]}
    assert set(by_workspace) == {str(WORKSPACE_A1), str(WORKSPACE_B1)}
    assert by_workspace[str(WORKSPACE_A1)]["roles"] == ["responder", "viewer"]
    assert by_workspace[str(WORKSPACE_A1)]["organization_name"] == "Alpha Bank"
    assert by_workspace[str(WORKSPACE_B1)]["roles"] == ["incident_commander"]
    assert "total" not in body["meta"]


def test_picker_pages_with_cursor(client: TestClient) -> None:
    first = client.get("/api/v1/me/workspaces?limit=1", headers=_auth("sub-amira")).json()
    cursor = first["meta"]["next_cursor"]
    second = client.get(
        f"/api/v1/me/workspaces?limit=1&cursor={cursor}", headers=_auth("sub-amira")
    ).json()

    seen = [item["workspace_id"] for item in first["data"] + second["data"]]
    assert sorted(seen) == sorted([str(WORKSPACE_A1), str(WORKSPACE_B1)])
    assert second["meta"]["next_cursor"] is None


@pytest.mark.parametrize(
    ("subject", "status", "code"),
    [("sub-suspended", 403, "USER_NOT_ACTIVE"), ("sub-stranger", 403, "USER_NOT_PROVISIONED")],
)
def test_picker_refuses_inactive_and_unknown_users(
    client: TestClient, subject: str, status: int, code: str
) -> None:
    response = client.get("/api/v1/me/workspaces", headers=_auth(subject))

    assert (response.status_code, response.json()["code"]) == (status, code)


def test_picker_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/me/workspaces").status_code == 401


def test_current_workspace_returns_details_and_roles(client: TestClient) -> None:
    response = client.get("/api/v1/workspaces/current", headers=_auth("sub-amira", WORKSPACE_A1))

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["workspace_key"] == "a-one"
    assert data["organization_id"] == str(ORG_A)
    assert data["roles"] == ["responder", "viewer"]


@pytest.mark.parametrize(
    ("subject", "workspace"),
    [
        ("sub-amira", WORKSPACE_A2),  # same organisation, no grant in this workspace
        ("sub-bob", WORKSPACE_A1),  # another organisation entirely
        ("sub-amira", uuid.uuid4()),  # does not exist
    ],
)
def test_current_workspace_denies_without_grant(
    client: TestClient, subject: str, workspace: uuid.UUID
) -> None:
    response = client.get("/api/v1/workspaces/current", headers=_auth(subject, workspace))

    assert (response.status_code, response.json()["code"]) == (403, "WORKSPACE_ACCESS_DENIED")
