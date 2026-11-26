"""Veryion licence keys against a real PostgreSQL: the SDK runs for real, only its HTTP is faked."""

import json
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import AnyHttpUrl, SecretStr
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from veryion_licensing import MemoryStorage, Veryion

from api_test_support import TEST_OIDC_AUDIENCE, TEST_OIDC_ISSUER
from db_test_support import (
    migrate_and_reset,
    require_test_database_url,
    run_as_probe_role,
    run_as_superuser,
)
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.modules.license.model import OrganizationLicense
from relyxus_api.modules.license.veryion_service import VeryionLicenseRuntime
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.modules.tenancy.model import Organization
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from relyxus_api.shared.config.settings import Environment, LicenseProvider, Settings
from tenancy_fixtures import (
    ORG_A,
    ORG_B,
    WORKSPACE_A1,
    WORKSPACE_B1,
    principal_for,
    seed_two_organisations_with_members,
)
from veryion_test_support import (
    GOLDEN,
    GOLDEN_KEY,
    KEY_SET,
    OTHER,
    OTHER_CUSTOMER_KEY,
    PRODUCT,
    START,
    TYPO_KEY,
    UNKNOWN_KEY,
    VERYION_URL,
    Clock,
    FakeVeryionServer,
    customer_uuid,
    iso,
    licence_uuid,
    token_payload,
)

pytestmark = pytest.mark.integration

INSTALL = "/api/v1/license/install"
STATUS = "/api/v1/license/status"


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)
    run_as_superuser(url, seed_two_organisations_with_members)
    return url


@pytest.fixture(autouse=True)
def _no_licences(database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with no licence and no bound customer; the device is a fixed test device."""
    monkeypatch.setenv("VY_TEST_DEVICE", "relyxus-integration")

    async def clear(session: AsyncSession) -> None:
        await session.execute(delete(OrganizationLicense))
        await session.execute(update(Organization).values(customer_id=None))

    run_as_superuser(database_url, clear)


@pytest.fixture
def server() -> FakeVeryionServer:
    return FakeVeryionServer(
        clock=Clock(), licences={GOLDEN_KEY: GOLDEN, OTHER_CUSTOMER_KEY: OTHER}
    )


class _SubjectTokenVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


def _settings(database_url: str) -> Settings:
    return Settings(
        environment=Environment.LOCAL,
        public_base_url=AnyHttpUrl("https://api.example.test"),
        database_url=SecretStr(database_url),
        database_probe_timeout_seconds=1.0,
        oidc_issuer_url=TEST_OIDC_ISSUER,
        oidc_audience=TEST_OIDC_AUDIENCE,
        license_provider=LicenseProvider.VERYION,
        veryion_product_code=PRODUCT,
        veryion_key_set=KEY_SET,
        veryion_allow_sandbox=True,
        veryion_api_base_url=AnyHttpUrl(VERYION_URL),
    )


type ClientMaker = Callable[[], TestClient]


@pytest.fixture
def make_client(database_url: str, server: FakeVeryionServer) -> ClientMaker:
    """A new app each call: a fresh runtime has no cached client, so it reads the database."""

    def build() -> TestClient:
        settings = _settings(database_url)
        app = create_app(settings)
        assert isinstance(app.state.license_runtime, VeryionLicenseRuntime)

        def client_factory(storage: MemoryStorage) -> Veryion:
            return Veryion(
                product=PRODUCT,
                keys=KEY_SET,
                allow_sandbox=True,
                storage=storage,
                api_base_url=VERYION_URL,
                send_hostname=False,
                timeout=5,
                clock=server.clock,
                http=server,
                auto_check_in=False,
            )

        app.state.license_runtime = VeryionLicenseRuntime(
            product_code=PRODUCT,
            key_set=KEY_SET,
            allow_sandbox=True,
            api_base_url=VERYION_URL,
            timeout_seconds=5,
            client_factory=client_factory,
        )
        app.state.access_token_verifier = _SubjectTokenVerifier()
        return TestClient(app)

    return build


def _headers(workspace: uuid.UUID = WORKSPACE_B1, subject: str = "sub-bob") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {subject}",
        WORKSPACE_HEADER: str(workspace),
        "Idempotency-Key": f"lic-{uuid.uuid4()}",
    }


def _install(client: TestClient, key: str) -> Any:
    return client.post(INSTALL, headers=_headers(), json={"licence_key": key})


def _stored(database_url: str, organization_id: uuid.UUID = ORG_B) -> list[OrganizationLicense]:
    async def read(session: AsyncSession) -> list[OrganizationLicense]:
        rows = await session.scalars(
            select(OrganizationLicense)
            .where(OrganizationLicense.organization_id == organization_id)
            .order_by(OrganizationLicense.created_at)
        )
        return list(rows.all())

    return run_as_superuser(database_url, read)


def _customer_of(database_url: str, organization_id: uuid.UUID) -> uuid.UUID | None:
    async def read(session: AsyncSession) -> uuid.UUID | None:
        organization = await session.get(Organization, organization_id)
        assert organization is not None
        return organization.customer_id

    return run_as_superuser(database_url, read)


def test_install_stores_only_the_sdk_state_and_binds_the_customer(
    make_client: ClientMaker, server: FakeVeryionServer, database_url: str
) -> None:
    response = _install(make_client(), GOLDEN_KEY)

    assert response.status_code == 201, response.text
    assert response.json()["data"]["state"] == "active"
    [record] = _stored(database_url)
    state = json.loads(record.artifact)
    assert GOLDEN_KEY not in record.artifact
    assert GOLDEN_KEY.replace("-", "") not in record.artifact.replace("-", "")
    assert state["format"] == 1
    assert state["product"] == PRODUCT
    assert state["licenceToken"].startswith("vy1.")
    assert state["activationToken"].startswith("vya1.")
    assert record.is_current is True
    assert record.license_id == licence_uuid(GOLDEN.licence)
    assert record.revision == 1
    assert _customer_of(database_url, ORG_B) == customer_uuid(GOLDEN.customer)
    assert server.calls == ["/v1/licence/activate"]


def test_status_reads_the_licence_back_from_the_database(
    make_client: ClientMaker, server: FakeVeryionServer, database_url: str
) -> None:
    assert _install(make_client(), GOLDEN_KEY).status_code == 201

    response = make_client().get(STATUS, headers=_headers())

    assert response.status_code == 200, response.text
    view = response.json()["data"]
    assert view["license_id"] == str(licence_uuid(GOLDEN.licence))
    assert view["state"] == "active"
    assert view["revision"] == 1
    assert view["entitlements"] == ["feature.replay", "seats"]
    assert view["expires_at"] == "2027-11-25T00:00:00Z"
    assert view["grace_ends_at"] == "2027-12-09T00:00:00Z"
    assert view["connected_refresh_source"] is None
    assert server.calls == ["/v1/licence/activate"]


def test_due_check_in_updates_the_stored_artifact(
    make_client: ClientMaker, server: FakeVeryionServer, database_url: str
) -> None:
    assert _install(make_client(), GOLDEN_KEY).status_code == 201
    [before] = _stored(database_url)
    server.clock.now = START + timedelta(hours=25)

    response = make_client().get(STATUS, headers=_headers())

    assert response.status_code == 200, response.text
    view = response.json()["data"]
    assert view["revision"] == 2
    assert view["connected_refresh_source"] == "live"
    assert server.calls == ["/v1/licence/activate", "/v1/licence/check-in"]
    [after] = _stored(database_url)
    assert after.id == before.id
    old_state, new_state = json.loads(before.artifact), json.loads(after.artifact)
    assert new_state["activationToken"] != old_state["activationToken"]
    assert token_payload(new_state["activationToken"])["issuedAt"] == iso(server.clock.now)
    assert token_payload(new_state["licenceToken"])["revision"] == 2
    assert new_state["lastCheckInAt"] == iso(server.clock.now)
    assert GOLDEN_KEY not in after.artifact

    # Read again: the check in is no longer due, so nothing is sent.
    again = make_client().get(STATUS, headers=_headers())
    assert again.json()["data"]["revision"] == 2
    assert server.calls == ["/v1/licence/activate", "/v1/licence/check-in"]


def test_install_for_another_customer_is_refused_and_frees_the_activation(
    make_client: ClientMaker, server: FakeVeryionServer, database_url: str
) -> None:
    client = make_client()
    assert _install(client, GOLDEN_KEY).status_code == 201

    response = _install(client, OTHER_CUSTOMER_KEY)

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "LICENSE_CUSTOMER_MISMATCH"
    assert server.calls == [
        "/v1/licence/activate",
        "/v1/licence/activate",
        "/v1/licence/deactivate",
    ]
    assert server.freed == {"ACT-0002"}
    assert server.activations["ACT-0002"] == OTHER.licence
    [record] = _stored(database_url)
    assert record.license_id == licence_uuid(GOLDEN.licence)
    assert record.is_current is True
    assert _customer_of(database_url, ORG_B) == customer_uuid(GOLDEN.customer)
    status = client.get(STATUS, headers=_headers()).json()["data"]
    assert status["license_id"] == str(licence_uuid(GOLDEN.licence))


def test_another_organisation_cannot_read_the_licence(
    make_client: ClientMaker, database_url: str
) -> None:
    client = make_client()
    assert _install(client, GOLDEN_KEY).status_code == 201

    other = client.get(STATUS, headers=_headers(WORKSPACE_A1, "sub-amira"))

    assert other.status_code == 404, other.text
    assert other.json()["code"] == "NO_LICENSE_INSTALLED"

    def visible_to(organization_id: uuid.UUID) -> Callable[[AsyncSession], Any]:
        async def count(session: AsyncSession) -> int:
            await apply_tenant_context(session, TenantContext(organization_id=organization_id))
            return len((await session.scalars(select(OrganizationLicense.id))).all())

        return count

    assert run_as_probe_role(database_url, visible_to(ORG_A)) == 0
    assert run_as_probe_role(database_url, visible_to(ORG_B)) == 1
    assert _customer_of(database_url, ORG_A) is None


@pytest.mark.parametrize(
    ("key", "is_offline", "expected"),
    [
        (UNKNOWN_KEY, False, (403, "LICENSE_KEY_REJECTED")),
        (TYPO_KEY, False, (403, "LICENSE_KEY_REJECTED")),
        (GOLDEN_KEY, True, (503, "LICENSE_SERVER_UNAVAILABLE")),
    ],
    ids=["unknown-key", "typo-key", "network-failure"],
)
def test_install_failures_store_nothing(
    make_client: ClientMaker,
    server: FakeVeryionServer,
    database_url: str,
    key: str,
    is_offline: bool,
    expected: tuple[int, str],
) -> None:
    server.is_offline = is_offline

    response = _install(make_client(), key)

    assert (response.status_code, response.json()["code"]) == expected, response.text
    assert _stored(database_url) == []
    assert _customer_of(database_url, ORG_B) is None
