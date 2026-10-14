"""HTTP surface for workspace audit logs (MPS-14.16)."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.modules.access.model import WorkspaceMembership
from relyxus_api.modules.audit.model import ActorType, AuditOutcome
from relyxus_api.modules.audit.service import AuditService, NewAuditEvent
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import (
    AMIRA,
    ORG_A,
    WORKSPACE_A1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)

    async def seed(session: AsyncSession) -> None:
        await seed_two_organisations_with_members(session)
        session.add(
            WorkspaceMembership(
                organization_id=ORG_A,
                workspace_id=WORKSPACE_A1,
                user_id=AMIRA,
                role="auditor",
            )
        )
        await apply_tenant_context(
            session, TenantContext(organization_id=ORG_A, workspace_id=WORKSPACE_A1)
        )
        service = AuditService()
        for index in range(3):
            await service.append(
                session,
                NewAuditEvent(
                    organization_id=ORG_A,
                    workspace_id=WORKSPACE_A1,
                    actor_type=ActorType.USER,
                    actor_user_id=AMIRA,
                    effective_user_id=None,
                    action=f"test.action.{index}",
                    target_type="test",
                    target_id=str(index),
                    outcome=AuditOutcome.SUCCEEDED,
                    before_state=None,
                    after_state={"index": index},
                    correlation_id="audit-http-test",
                    occurred_at=datetime(2026, 10, 14, 10, index, 0, tzinfo=UTC),
                ),
            )

    run_as_superuser(url, seed)
    return url


class _SubjectTokenVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_app(make_settings(database_url=database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    return TestClient(app)


def _auth(subject: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(WORKSPACE_A1),
    }


def test_list_audit_events_returns_workspace_chain(client: TestClient) -> None:
    body = client.get("/api/v1/audit-events", headers=_auth("sub-amira")).json()

    assert body["success"] is True
    assert len(body["data"]) == 3
    assert body["data"][0]["sequence"] == 1
    assert body["data"][-1]["action"] == "test.action.2"
    assert "total" not in body["meta"]


def test_list_audit_events_pages(client: TestClient) -> None:
    first = client.get("/api/v1/audit-events?limit=2", headers=_auth("sub-amira")).json()
    cursor = first["meta"]["next_cursor"]
    second = client.get(
        f"/api/v1/audit-events?limit=2&cursor={cursor}", headers=_auth("sub-amira")
    ).json()

    sequences = [item["sequence"] for item in first["data"] + second["data"]]
    assert sequences == [1, 2, 3]
    assert second["meta"]["next_cursor"] is None


def test_chain_verification_reports_valid(client: TestClient) -> None:
    body = client.get("/api/v1/audit-events/chain-verification", headers=_auth("sub-amira")).json()[
        "data"
    ]

    assert body["is_valid"] is True
    assert body["chain_id"] == str(WORKSPACE_A1)
    assert body["failures"] == []


def test_list_audit_events_requires_workspace_header(client: TestClient) -> None:
    response = client.get("/api/v1/audit-events", headers={"Authorization": "Bearer sub-amira"})

    assert response.status_code == 422
