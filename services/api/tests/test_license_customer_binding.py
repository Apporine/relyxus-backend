"""Licence install must match the organisation customer_id when bound."""

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
from tenancy_fixtures import ORG_B, WORKSPACE_B1, principal_for, seed_two_organisations_with_members

pytestmark = pytest.mark.integration

GOLDEN_VECTOR = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "packages/licensing/tests/vectors/golden-license-v1.json"
    ).read_text(encoding="utf-8")
)
OTHER_CUSTOMER = uuid.uuid4()


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)

    async def seed(session: AsyncSession) -> None:
        await seed_two_organisations_with_members(session)
        org = await session.get(Organization, ORG_B)
        assert org is not None
        org.customer_id = OTHER_CUSTOMER

    run_as_superuser(url, seed)
    return url


def _settings(database_url: str) -> Settings:
    return Settings(
        environment=Environment.LOCAL,
        public_base_url=AnyHttpUrl("https://api.example.test"),
        database_url=SecretStr(database_url),
        database_probe_timeout_seconds=1.0,
        oidc_issuer_url=TEST_OIDC_ISSUER,
        oidc_audience=TEST_OIDC_AUDIENCE,
        license_trusted_key_set_path=str(
            Path(__file__).resolve().parents[3]
            / "packages/licensing/tests/vectors/golden-trusted-key-set-v1.json"
        ),
        license_customer_id=GOLDEN_VECTOR["payload"]["customer_id"],
        license_deployment_id="golden-bank-prod",
        license_key_environment="production",
    )


class _SubjectTokenVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_app(_settings(database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    return TestClient(app)


def test_install_rejects_wrong_customer(client: TestClient) -> None:
    headers = {
        "Authorization": "Bearer sub-bob",
        WORKSPACE_HEADER: str(WORKSPACE_B1),
        "Idempotency-Key": f"lic-{uuid.uuid4()}",
    }
    response = client.post(
        "/api/v1/license/install",
        headers=headers,
        json={"artifact": GOLDEN_VECTOR["envelope"]},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "LICENSE_CUSTOMER_MISMATCH"
