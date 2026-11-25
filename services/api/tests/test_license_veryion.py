"""Veryion licence keys behind /license (RELYXUS_LICENSE_PROVIDER=veryion)."""

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from veryion_licensing import (
    CheckInResult,
    Customer,
    Edition,
    MemoryStorage,
    Verified,
    VeryionError,
)

from relyxus_api.modules.license.model import OrganizationLicense
from relyxus_api.modules.license.provider import LicenseRequestMismatchError, install_license
from relyxus_api.modules.license.schema import InstallLicenseRequest
from relyxus_api.modules.license.service import LicenseCustomerMismatchError, LicenseRuntime
from relyxus_api.modules.license.veryion_service import (
    LicenseKeyRejectedError,
    LicenseServerUnavailableError,
    VeryionLicenseRuntime,
    VeryionLicenseService,
)

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
KEY = "ABCD-EFGH-JKLM-NPQR-STUV"


def _verified(**changes: object) -> Verified:
    values: dict[str, object] = {
        "valid": True,
        "reason": None,
        "state": "active",
        "read_only": False,
        "licence": "LIC-GDQ89A",
        "revision": 1,
        "product": "RLX",
        "environment": "sandbox",
        "customer": Customer("CUS-NYA95A", "Golden Bank"),
        "edition": Edition("STD", "Standard"),
        "model": "subscription",
        "entitlements": {"feature.replay": True, "feature.export": False, "seats": 25},
        "starts": "2026-11-25T00:00:00Z",
        "expires": "2026-12-15T00:00:00Z",
        "grace_until": "2026-12-20T00:00:00Z",
        "maintenance_until": None,
        "slot": 1,
        "limit": None,
        "lease_until": "2026-12-09T12:00:00Z",
        "device_match": 100,
        "check_in_due": False,
    }
    values.update(changes)
    return Verified(**values)  # type: ignore[arg-type]


class FakeClient:
    """Stands in for veryion_licensing.Veryion: answers are set per test."""

    def __init__(self, storage: MemoryStorage) -> None:
        self.storage = storage
        self.result = _verified()
        self.after_check_in: Verified | None = None
        self.activate_error: VeryionError | None = None
        self.check_ins = 0
        self.deactivated = False

    def init(self) -> None:
        return None

    def verify(self) -> Verified:
        return self.result

    def activate(self, licence_key: str) -> Verified:
        if self.activate_error is not None:
            raise self.activate_error
        self.storage.write('{"format": 1, "licenceToken": "vy1.signed"}')
        return self.result

    def check_in(self) -> CheckInResult:
        self.check_ins += 1
        self.storage.write('{"format": 1, "licenceToken": "vy1.renewed"}')
        if self.after_check_in is not None:
            self.result = self.after_check_in
        return CheckInResult("unchanged", self.result)

    def deactivate(self) -> None:
        self.deactivated = True


def _runtime(prepare: object = None) -> tuple[VeryionLicenseRuntime, list[FakeClient]]:
    made: list[FakeClient] = []

    def factory(storage: MemoryStorage) -> FakeClient:
        client = FakeClient(storage)
        if callable(prepare):
            prepare(client)
        made.append(client)
        return client

    runtime = VeryionLicenseRuntime(
        product_code="RLX",
        key_set="vyk1.test",
        allow_sandbox=True,
        api_base_url="https://api.veryion.com",
        timeout_seconds=10,
        client_factory=factory,  # type: ignore[arg-type]
    )
    return runtime, made


def _record(organization_id: uuid.UUID, artifact: str = '{"format": 1}') -> OrganizationLicense:
    return OrganizationLicense(
        id=uuid.uuid4(),
        organization_id=organization_id,
        license_id=uuid.uuid4(),
        revision=1,
        artifact=artifact,
        is_current=True,
        superseded_at=None,
    )


def _repository(current: OrganizationLicense | None) -> MagicMock:
    repository = MagicMock()
    repository.find_current = AsyncMock(return_value=current)
    repository.mark_superseded_now = AsyncMock()
    repository.add_record = AsyncMock(side_effect=lambda _session, record: record)
    return repository


def test_status_verifies_locally_and_lists_entitlements_that_are_on() -> None:
    organization_id = uuid.uuid4()
    record = _record(organization_id)
    runtime, made = _runtime()
    service = VeryionLicenseService(repository=_repository(record))

    view = asyncio.run(service.status(AsyncMock(), organization_id, runtime, NOW))

    assert view.state == "active"
    assert view.entitlements == ("feature.replay", "seats")
    assert view.expires_at == datetime(2026, 12, 15, tzinfo=UTC)
    assert view.grace_ends_at == datetime(2026, 12, 20, tzinfo=UTC)
    assert view.connected_refresh_source is None
    assert made[0].check_ins == 0
    assert record.artifact == '{"format": 1}'


def test_status_checks_in_when_due_and_stores_the_new_tokens() -> None:
    organization_id = uuid.uuid4()
    record = _record(organization_id)

    def due(client: FakeClient) -> None:
        client.result = _verified(check_in_due=True)
        client.after_check_in = _verified(revision=2)

    runtime, made = _runtime(due)
    session = AsyncMock()
    service = VeryionLicenseService(repository=_repository(record))

    view = asyncio.run(service.status(session, organization_id, runtime, NOW))

    assert made[0].check_ins == 1
    assert view.revision == 2
    assert view.connected_refresh_source == "live"
    assert record.artifact == '{"format": 1, "licenceToken": "vy1.renewed"}'
    session.flush.assert_awaited()


def test_status_reuses_the_client_while_the_stored_state_is_unchanged() -> None:
    organization_id = uuid.uuid4()
    record = _record(organization_id)
    runtime, made = _runtime()
    service = VeryionLicenseService(repository=_repository(record))

    asyncio.run(service.status(AsyncMock(), organization_id, runtime, NOW))
    asyncio.run(service.status(AsyncMock(), organization_id, runtime, NOW))
    record.artifact = '{"format": 1, "changed": "by another worker"}'
    asyncio.run(service.status(AsyncMock(), organization_id, runtime, NOW))

    assert len(made) == 2


@pytest.mark.parametrize(
    ("result", "state", "reason"),
    [
        (_verified(state="in_grace"), "grace", None),
        (_verified(valid=False, reason="expired", state="expired"), "expired", "expired"),
        (
            _verified(valid=False, reason="suspended", state=None, expires=None, grace_until=None),
            "suspended",
            "suspended",
        ),
        (
            _verified(valid=False, reason="revoked", state=None, expires=None, grace_until=None),
            "revoked",
            "revoked",
        ),
        (
            _verified(
                valid=False, reason="wrong_device", state=None, expires=None, grace_until=None
            ),
            "invalid",
            "wrong_device",
        ),
    ],
)
def test_status_maps_veryion_states(result: Verified, state: str, reason: str | None) -> None:
    organization_id = uuid.uuid4()

    def answer(client: FakeClient) -> None:
        client.result = result

    runtime, _ = _runtime(answer)
    service = VeryionLicenseService(repository=_repository(_record(organization_id)))

    view = asyncio.run(service.status(AsyncMock(), organization_id, runtime, NOW))

    assert (view.state, view.reason) == (state, reason)


def test_install_activates_binds_the_customer_and_stores_the_tokens_not_the_key() -> None:
    organization_id = uuid.uuid4()
    organization = MagicMock(customer_id=None)
    session = AsyncMock()
    session.get = AsyncMock(return_value=organization)
    repository = _repository(None)
    runtime, _ = _runtime()

    view = asyncio.run(
        VeryionLicenseService(repository=repository).install(
            session, organization_id, KEY, runtime, NOW
        )
    )

    record = repository.add_record.await_args.args[1]
    assert KEY not in record.artifact
    assert record.artifact == '{"format": 1, "licenceToken": "vy1.signed"}'
    assert record.license_id == uuid.uuid5(
        uuid.NAMESPACE_URL, "https://veryion.com/licences/LIC-GDQ89A"
    )
    assert organization.customer_id == uuid.uuid5(
        uuid.NAMESPACE_URL, "https://veryion.com/customers/CUS-NYA95A"
    )
    assert view.state == "active"
    repository.mark_superseded_now.assert_awaited_once()


def test_install_for_another_customer_is_refused_and_frees_the_activation() -> None:
    organization_id = uuid.uuid4()
    session = AsyncMock()
    session.get = AsyncMock(return_value=MagicMock(customer_id=uuid.uuid4()))
    runtime, made = _runtime()

    with pytest.raises(LicenseCustomerMismatchError):
        asyncio.run(
            VeryionLicenseService(repository=_repository(None)).install(
                session, organization_id, KEY, runtime, NOW
            )
        )

    assert made[0].deactivated is True


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("invalid_licence_key", LicenseKeyRejectedError),
        ("licence_not_active", LicenseKeyRejectedError),
        ("network_error", LicenseServerUnavailableError),
        ("timeout", LicenseServerUnavailableError),
    ],
)
def test_install_maps_sdk_errors(code: str, expected: type[Exception]) -> None:
    def failing(client: FakeClient) -> None:
        client.activate_error = VeryionError(code, "refused")

    runtime, _ = _runtime(failing)

    with pytest.raises(expected):
        asyncio.run(
            VeryionLicenseService(repository=_repository(None)).install(
                AsyncMock(), uuid.uuid4(), KEY, runtime, NOW
            )
        )


def test_install_request_takes_exactly_one_credential() -> None:
    assert InstallLicenseRequest(licence_key=KEY).licence_key == KEY
    with pytest.raises(ValidationError):
        InstallLicenseRequest()
    with pytest.raises(ValidationError):
        InstallLicenseRequest(artifact="{}", licence_key=KEY)


def test_install_with_the_wrong_credential_for_the_provider_is_refused() -> None:
    runtime, _ = _runtime()
    apporine = LicenseRuntime(verifier=MagicMock(), key_set=MagicMock(), installation=MagicMock())

    with pytest.raises(LicenseRequestMismatchError):
        asyncio.run(
            install_license(
                AsyncMock(), uuid.uuid4(), InstallLicenseRequest(artifact="{}"), runtime, NOW
            )
        )
    with pytest.raises(LicenseRequestMismatchError):
        asyncio.run(
            install_license(
                AsyncMock(), uuid.uuid4(), InstallLicenseRequest(licence_key=KEY), apporine, NOW
            )
        )
