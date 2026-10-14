"""Identity → user → workspace grant → tenant context (MP-10.01, Q-18)."""

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from api_test_support import get_test_database_url, make_settings
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
from relyxus_api.modules.tenancy.model import Organization, Workspace
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from relyxus_api.shared.db.engine import create_session_factory

pytestmark = pytest.mark.integration
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
PROBE_ROLE = "relyxus_rls_probe"
ISSUER = "https://id.example.test/realms/relyxus"
ORG_A, ORG_B = uuid.uuid4(), uuid.uuid4()
WORKSPACE_A1, WORKSPACE_A2, WORKSPACE_B1 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
AMIRA, SUSPENDED, BOB = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def _principal(subject: str, issuer: str = ISSUER) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        issuer=issuer, subject=subject, email=None, display_name=None, authenticated_at=None
    )


@pytest.fixture(scope="module")
def database_url() -> str:
    url = get_test_database_url()
    if url is None:
        if os.environ.get("RELYXUS_REQUIRE_INTEGRATION") == "1":
            pytest.fail("RELYXUS_TEST_DATABASE_URL is required in this environment")
        pytest.skip("RELYXUS_TEST_DATABASE_URL not set")
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    asyncio.run(_seed(url))
    return url


async def _seed(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{PROBE_ROLE}')"
                f" THEN CREATE ROLE {PROBE_ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF; END $$"
            )
        )
        await connection.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON organizations, workspaces, users,"
                f" workspace_memberships TO {PROBE_ROLE}"
            )
        )
        for table in ("workspace_memberships", "users", "workspaces", "organizations"):
            await connection.execute(text(f"DELETE FROM {table}"))  # noqa: S608
    async with create_session_factory(engine)() as session, session.begin():
        for org_id, name in ((ORG_A, "alpha"), (ORG_B, "bravo")):
            session.add(
                Organization(
                    id=org_id, name=name, deployment_mode="saas", default_region="eu-west-2"
                )
            )
        await session.flush()
        for ws_id, org_id, key in (
            (WORKSPACE_A1, ORG_A, "a-one"),
            (WORKSPACE_A2, ORG_A, "a-two"),
            (WORKSPACE_B1, ORG_B, "b-one"),
        ):
            session.add(
                Workspace(
                    id=ws_id,
                    organization_id=org_id,
                    key=key,
                    name=key,
                    data_residency_region="eu-west-2",
                )
            )
        for user_id, subject, status in (
            (AMIRA, "sub-amira", "active"),
            (SUSPENDED, "sub-suspended", "suspended"),
            (BOB, "sub-bob", "active"),
        ):
            session.add(
                User(
                    id=user_id,
                    idp_issuer=ISSUER,
                    idp_subject=subject,
                    email=None,
                    display_name=None,
                    status=status,
                )
            )
        await session.flush()
        for org_id, ws_id, user_id, role in (
            (ORG_A, WORKSPACE_A1, AMIRA, "responder"),
            (ORG_A, WORKSPACE_A1, AMIRA, "viewer"),
            (ORG_A, WORKSPACE_A1, SUSPENDED, "viewer"),
            (ORG_B, WORKSPACE_B1, BOB, "admin"),
        ):
            session.add(
                WorkspaceMembership(
                    organization_id=org_id, workspace_id=ws_id, user_id=user_id, role=role
                )
            )
    await engine.dispose()


def _as_probe_role[ResultT](
    url: str, work: Callable[[AsyncSession], Awaitable[ResultT]]
) -> ResultT:
    async def run() -> ResultT:
        engine = create_async_engine(url)
        try:
            async with create_session_factory(engine)() as session, session.begin():
                await session.execute(text(f"SET LOCAL ROLE {PROBE_ROLE}"))
                return await work(session)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _open(url: str, subject: str, workspace_id: uuid.UUID) -> WorkspaceAccess:
    service = WorkspaceAccessService(AccessRepository())
    return _as_probe_role(
        url, lambda s: service.open_workspace(s, _principal(subject), workspace_id)
    )


def test_member_gets_roles_and_tenant_scope(database_url: str) -> None:
    async def open_then_list(session: AsyncSession) -> tuple[WorkspaceAccess, set[uuid.UUID]]:
        access = await WorkspaceAccessService(AccessRepository()).open_workspace(
            session, _principal("sub-amira"), WORKSPACE_A1
        )
        return access, set((await session.scalars(select(Workspace.id))).all())

    access, visible = _as_probe_role(database_url, open_then_list)

    assert access.organization_id == ORG_A
    assert access.roles == {WorkspaceRole.RESPONDER, WorkspaceRole.VIEWER}
    assert visible == {WORKSPACE_A1, WORKSPACE_A2}


@pytest.mark.parametrize("workspace_id", [WORKSPACE_B1, uuid.uuid4()])
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
        _as_probe_role(
            database_url,
            lambda s: service.open_workspace(
                s, _principal("sub-amira", "https://evil.example/realms/x"), WORKSPACE_A1
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
        await repository.list_workspace_grants(session, user.id, WORKSPACE_A1)
        users = await session.scalar(select(func.count()).select_from(User))
        grants = await session.scalar(select(func.count()).select_from(WorkspaceMembership))
        return users or 0, grants or 0

    assert _as_probe_role(database_url, count_visible) == (1, 2)


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
        _as_probe_role(database_url, insert_user)


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
        return _principal(token)


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
    assert get("sub-amira", str(WORKSPACE_B1)) == (403, "WORKSPACE_ACCESS_DENIED")
    assert get("sub-amira", str(WORKSPACE_A1)) == (200, ["responder", "viewer"])
