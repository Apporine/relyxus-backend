import asyncio
import json
import uuid
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from api_test_support import TEST_OIDC_AUDIENCE, TEST_OIDC_ISSUER
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import LICENSE_READINESS_PROBE_NAME, create_app
from relyxus_api.modules.license.service import LicenseRuntime, LicenseService
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.modules.tenancy.model import Organization
from relyxus_api.shared.config.settings import Environment, Settings
from tenancy_fixtures import ORG_B, seed_two_organisations_with_members

pytestmark = pytest.mark.integration

GOLDEN_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages/licensing/tests/vectors/golden-license-v1.json"
)
GOLDEN = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)

    async def seed(session: AsyncSession) -> None:
        await seed_two_organisations_with_members(session)
        org = await session.get(Organization, ORG_B)
        assert org is not None
        org.customer_id = uuid.UUID(GOLDEN["payload"]["customer_id"])

    run_as_superuser(url, seed)
    return url


def _settings(database_url: str, org_id: uuid.UUID) -> Settings:
    return Settings(
        environment=Environment.LOCAL,
        public_base_url=AnyHttpUrl("https://api.example.test"),
        database_url=SecretStr(database_url),
        database_probe_timeout_seconds=1.0,
        oidc_issuer_url=TEST_OIDC_ISSUER,
        oidc_audience=TEST_OIDC_AUDIENCE,
        license_trusted_key_vector_path=str(GOLDEN_PATH),
        license_customer_id=GOLDEN["payload"]["customer_id"],
        license_deployment_id="golden-bank-prod",
        license_key_environment="production",
        license_readiness_organization_id=org_id,
    )


def test_readiness_includes_commercial_license_probe(database_url: str) -> None:
    async def exercise() -> None:
        app = create_app(_settings(database_url, ORG_B))
        report = await app.state.health_service.get_readiness()
        names = {check.name for check in report.checks}
        assert LICENSE_READINESS_PROBE_NAME in names
        license_check = next(c for c in report.checks if c.name == LICENSE_READINESS_PROBE_NAME)
        assert license_check.is_reachable is False

        runtime: LicenseRuntime | None = app.state.license_runtime
        assert runtime is not None
        session_factory = app.state.session_factory
        async with session_factory() as session, session.begin():
            await apply_tenant_context(
                session, TenantContext(organization_id=ORG_B, workspace_id=None)
            )
            await LicenseService().install(session, ORG_B, GOLDEN["envelope"], runtime)

        report_after = await app.state.health_service.get_readiness()
        license_check_after = next(
            c for c in report_after.checks if c.name == LICENSE_READINESS_PROBE_NAME
        )
        assert license_check_after.is_reachable is True

    asyncio.run(exercise())
