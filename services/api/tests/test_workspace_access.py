"""Identity → user → workspace grant → tenant context (MP-10.01, Q-18)."""

import asyncio
import uuid

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from api_test_support import make_settings
from db_test_support import (
    migrate_and_reset,
    require_test_database_url,
    run_as_probe_role,
    run_as_superuser,
)
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER, WorkspaceSessionDependency
from relyxus_api.modules.access.model import User, WorkspaceMembership, WorkspaceRole
from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.service import (
    UserNotActiveError,
    UserNotProvisionedError,
    WorkspaceAccess,
    WorkspaceAccessDeniedError,
    WorkspaceAccessService,
)
from relyxus_api.modules.tenancy.model import Workspace
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from relyxus_api.shared.db.engine import create_session_factory
from tenancy_fixtures import (
    BOB,
    ISSUER,
    ORG_A,
    ORG_B,
    WORKSPACE_A1,
    WORKSPACE_A2,
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


def _open(url: str, subject: str, workspace_id: uuid.UUID) -> WorkspaceAccess:
    service = WorkspaceAccessService(AccessRepository())
    return run_as_probe_role(
        url, lambda s: service.open_workspace(s, principal_for(subject), workspace_id)
    )


def test_member_gets_roles_and_tenant_scope(database_url: str) -> None:
    async def open_then_list(session: AsyncSession) -> tuple[WorkspaceAccess, set[uuid.UUID]]:
        access = await WorkspaceAccessService(AccessRepository()).open_workspace(
            session, principal_for("sub-amira"), WORKSPACE_A1
        )
        return access, set((await session.scalars(select(Workspace.id))).all())

    access, visible = run_as_probe_role(database_url, open_then_list)

    assert access.organization_id == ORG_A
    assert access.roles == {WorkspaceRole.RESPONDER, WorkspaceRole.VIEWER}
    assert visible == {WORKSPACE_A1, WORKSPACE_A2}


@pytest.mark.parametrize("workspace_id", [WORKSPACE_A2, uuid.uuid4()])
def test_foreign_and_unknown_workspaces_fail_identically(
    database_url: str, workspace_id: uuid.UUID
) -> None:
    with pytest.raises(
        WorkspaceAccessDeniedError, match=r"You do not have access to this workspace\."
    ):
        _open(database_url, "sub-amira", workspace_id)


def test_unknown_identity_is_not_provisioned(database_url: str) -> None:
    with pytest.raises(UserNotProvisionedError):
        _open(database_url, "sub-stranger", WORKSPACE_A1)


def test_same_subject_from_another_issuer_is_a_different_identity(database_url: str) -> None:
    service = WorkspaceAccessService(AccessRepository())
    with pytest.raises(UserNotProvisionedError):
        run_as_probe_role(
            database_url,
            lambda s: service.open_workspace(
                s, principal_for("sub-amira", "https://evil.example/realms/x"), WORKSPACE_A1
            ),
        )


def test_suspended_user_has_no_access_despite_grants(database_url: str) -> None:
    with pytest.raises(UserNotActiveError):
        _open(database_url, "sub-suspended", WORKSPACE_A1)


def test_identity_context_reveals_only_own_user_and_grants(database_url: str) -> None:
    async def count_visible(session: AsyncSession) -> tuple[int, int]:
        repository = AccessRepository()
        user = await repository.find_user_by_identity(session, ISSUER, "sub-amira")
        assert user is not None
        await repository.apply_user_context(session, user.id)
        users = await session.scalar(select(func.count()).select_from(User))
        grants = await session.scalar(select(func.count()).select_from(WorkspaceMembership))
        return users or 0, grants or 0

    assert run_as_probe_role(database_url, count_visible) == (1, 3)


def test_application_role_cannot_create_users_for_others(database_url: str) -> None:
    async def insert_user(session: AsyncSession) -> None:
        session.add(
            User(
                idp_issuer=ISSUER,
                idp_subject="sub-injected",
                email=None,
                display_name=None,
                status="active",
            )
        )
        await session.flush()

    with pytest.raises(DBAPIError, match="row-level security"):
        run_as_probe_role(database_url, insert_user)


def test_membership_cannot_point_at_another_organisations_workspace(database_url: str) -> None:
    async def insert_mismatched() -> None:
        engine = create_async_engine(database_url)
        try:
            async with create_session_factory(engine)() as session, session.begin():
                session.add(
                    WorkspaceMembership(
                        organization_id=ORG_B, workspace_id=WORKSPACE_A1, user_id=BOB, role="admin"
                    )
                )
        finally:
            await engine.dispose()

    with pytest.raises(IntegrityError):
        asyncio.run(insert_mismatched())


class _SubjectTokenVerifier:
    """Test double: the bearer token is the subject itself."""

    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_app(make_settings(database_url=database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    router = APIRouter()

    @router.get("/probe/workspace-roles")
    def read_roles(workspace: WorkspaceSessionDependency) -> list[str]:
        return sorted(workspace.access.roles)

    app.include_router(router)
    return TestClient(app)


def test_http_flow_requires_token_header_and_grant(client: TestClient) -> None:
    def get(token: str | None, workspace: str | None) -> tuple[int, object]:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if workspace:
            headers[WORKSPACE_HEADER] = workspace
        response = client.get("/probe/workspace-roles", headers=headers)
        body = response.json()
        return response.status_code, body.get("code") if isinstance(body, dict) else body

    assert get(None, str(WORKSPACE_A1)) == (401, "AUTHENTICATION_REQUIRED")
    assert get("sub-amira", None) == (422, "VALIDATION_FAILED")
    assert get("sub-amira", "not-a-uuid") == (422, "VALIDATION_FAILED")
    assert get("sub-amira", str(WORKSPACE_A2)) == (403, "WORKSPACE_ACCESS_DENIED")
    assert get("sub-bob", str(WORKSPACE_A1)) == (403, "WORKSPACE_ACCESS_DENIED")
    assert get("sub-amira", str(WORKSPACE_A1)) == (200, ["responder", "viewer"])
