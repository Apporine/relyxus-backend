"""Organisation licence install and status (LIC-7.07, DEP-23.07)."""

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import AnyHttpUrl, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from api_test_support import TEST_OIDC_AUDIENCE, TEST_OIDC_ISSUER
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.modules.tenancy.model import Organization
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from relyxus_api.shared.config.settings import Environment, Settings
from tenancy_fixtures import (
    ORG_B,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_VECTOR_PATH = REPO_ROOT / "packages/licensing/tests/vectors/golden-license-v1.json"
GOLDEN_VECTOR = json.loads(GOLDEN_VECTOR_PATH.read_text(encoding="utf-8"))


def _license_settings(database_url: str) -> Settings:
    return Settings(
        environment=Environment.LOCAL,
        public_base_url=AnyHttpUrl("https://api.example.test"),
        database_url=SecretStr(database_url),
        database_probe_timeout_seconds=1.0,
        oidc_issuer_url=TEST_OIDC_ISSUER,
        oidc_audience=TEST_OIDC_AUDIENCE,
        license_trusted_key_vector_path=str(GOLDEN_VECTOR_PATH),
        license_customer_id=GOLDEN_VECTOR["payload"]["customer_id"],
        license_deployment_id="golden-bank-prod",
        license_key_environment="production",
    )


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)

    async def bind_customer(session: AsyncSession) -> None:
        await seed_two_organisations_with_members(session)
        org = await session.get(Organization, ORG_B)
        assert org is not None
        org.customer_id = uuid.UUID(GOLDEN_VECTOR["payload"]["customer_id"])

    run_as_superuser(url, bind_customer)
    return url


class _SubjectTokenVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_app(_license_settings(database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    return TestClient(app)


def _admin_headers(idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": "Bearer sub-bob",
        WORKSPACE_HEADER: str(WORKSPACE_B1),
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def test_install_and_read_license_status(client: TestClient) -> None:
    key = f"lic-{uuid.uuid4()}"
    install = client.post(
        "/api/v1/license/install",
        headers=_admin_headers(key),
        json={"artifact": GOLDEN_VECTOR["envelope"]},
    )
    assert install.status_code == 201
    status = client.get("/api/v1/license/status", headers=_admin_headers()).json()["data"]
    assert status["state"] == "active"
    assert status["revision"] == GOLDEN_VECTOR["payload"]["revision"]
