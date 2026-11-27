"""Veryion licence keys behind /license (RELYXUS_LICENSE_PROVIDER=veryion).

The server activates the organisation's licence key once with Veryion, then keeps only the signed
licence and activation tokens (the SDK state, never the key) in `organization_licenses.artifact`.
Every status read verifies those tokens locally; the server checks in with Veryion only when the
activation's lease says it is due.
"""

import asyncio
import contextlib
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession
from veryion_licensing import MemoryStorage, Verified, Veryion, VeryionError

from relyxus_api.modules.license.model import OrganizationLicense
from relyxus_api.modules.license.repository import LicenseRepository
from relyxus_api.modules.license.schema import LicenseStatusView
from relyxus_api.modules.license.service import (
    LicenseCustomerMismatchError,
    LicenseDowngradeForbiddenError,
    NoLicenseInstalledError,
)
from relyxus_api.modules.tenancy.model import Organization
from relyxus_api.shared.errors.app_errors import DependencyUnavailableError, LicenseProblemError
from relyxus_api.shared.utils.ids import new_uuid7

# Veryion licence and customer IDs are public IDs (LIC-..., CUS-...); the tables key them as UUIDs.
_ID_NAMESPACE = "https://veryion.com/"
# SDK error codes that mean "Veryion could not be asked", not "the key is wrong".
_UNAVAILABLE_CODES = frozenset(
    {"network_error", "timeout", "server_error", "rate_limited", "server_response_invalid"}
)


class LicenseKeyRejectedError(LicenseProblemError):
    code: ClassVar[str] = "LICENSE_KEY_REJECTED"


class LicenseServerUnavailableError(DependencyUnavailableError):
    code: ClassVar[str] = "LICENSE_SERVER_UNAVAILABLE"


def _app_version() -> str | None:
    try:
        return version("relyxus-api")
    except PackageNotFoundError:
        return None


@dataclass
class VeryionLicenseRuntime:
    """One Veryion client per organisation, rebuilt when the stored state changed under it."""

    product_code: str
    key_set: str
    allow_sandbox: bool
    api_base_url: str
    timeout_seconds: float
    client_factory: Callable[[MemoryStorage], Veryion] | None = None
    _clients: dict[uuid.UUID, tuple[Veryion, MemoryStorage]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        if self.client_factory is None:
            # One client, no fingerprint collected: a wrong key set stops the app at startup.
            self._build(MemoryStorage())

    def _build(self, storage: MemoryStorage) -> Veryion:
        if self.client_factory is not None:
            return self.client_factory(storage)
        return Veryion(
            product=self.product_code,
            keys=self.key_set,
            allow_sandbox=self.allow_sandbox,
            storage=storage,
            api_base_url=self.api_base_url,
            send_hostname=False,
            app_version=_app_version(),
            timeout=self.timeout_seconds,
            auto_check_in=False,
        )

    def new_client(self, state: str | None) -> tuple[Veryion, MemoryStorage]:
        storage = MemoryStorage(state)
        client = self._build(storage)
        client.init()
        return client, storage

    def client_for(self, organization_id: uuid.UUID, state: str) -> tuple[Veryion, MemoryStorage]:
        with self._lock:
            cached = self._clients.get(organization_id)
        if cached is not None and cached[1].text == state:
            return cached
        built = self.new_client(state)
        self.remember(organization_id, built)
        return built

    def remember(self, organization_id: uuid.UUID, built: tuple[Veryion, MemoryStorage]) -> None:
        with self._lock:
            self._clients[organization_id] = built


def _uuid_of(kind: str, public_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{_ID_NAMESPACE}{kind}/{public_id}")


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _state_of(result: Verified) -> str:
    if result.valid:
        return "grace" if result.state == "in_grace" else (result.state or "active")
    if result.reason in ("expired", "superseded", "suspended", "revoked"):
        return result.reason
    return "invalid"


def _view(
    record: OrganizationLicense, result: Verified, at: datetime, source: str | None
) -> LicenseStatusView:
    entitlements = tuple(sorted(key for key in (result.entitlements or {}) if result.has(key)))
    expires = _time(result.expires)
    return LicenseStatusView(
        license_id=record.license_id,
        revision=result.revision if result.revision is not None else record.revision,
        state=_state_of(result),
        reason=result.reason,
        expires_at=expires,
        grace_ends_at=_time(result.grace_until) or expires,
        entitlements=entitlements,
        evaluated_at=at,
        connected_refresh_source=source,
    )


def _rejected(error: VeryionError) -> Exception:
    if error.code in _UNAVAILABLE_CODES:
        return LicenseServerUnavailableError(f"Veryion could not be reached: {error}")
    return LicenseKeyRejectedError(str(error))


class VeryionLicenseService:
    def __init__(self, repository: LicenseRepository | None = None) -> None:
        self._repository = repository or LicenseRepository()

    async def status(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        runtime: VeryionLicenseRuntime,
        now: datetime | None = None,
    ) -> LicenseStatusView:
        record = await self._repository.find_current(session, organization_id)
        if record is None:
            raise NoLicenseInstalledError("No licence is installed for this organisation.")
        client, storage = await asyncio.to_thread(
            runtime.client_for, organization_id, record.artifact
        )
        result = client.verify()
        source: str | None = None
        if result.check_in_due:
            try:
                outcome = await asyncio.to_thread(client.check_in)
                source = "live" if outcome.status in ("updated", "unchanged") else None
            except VeryionError:
                # A refused check in (device_mismatch) already updated the SDK state.
                source = None
            result = client.verify()
        if storage.text is not None and storage.text != record.artifact:
            record.artifact = storage.text
            await session.flush()
        return _view(record, result, now or datetime.now(UTC), source)

    async def install(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        licence_key: str,
        runtime: VeryionLicenseRuntime,
        now: datetime | None = None,
    ) -> LicenseStatusView:
        built = await asyncio.to_thread(runtime.new_client, None)
        client, storage = built
        try:
            result = await asyncio.to_thread(client.activate, licence_key)
        except VeryionError as error:
            raise _rejected(error) from error
        try:
            record = await self._record(session, organization_id, result, storage)
        except Exception:
            # The activation must not hold a slot for a licence this organisation may not use.
            with contextlib.suppress(VeryionError):
                await asyncio.to_thread(client.deactivate)
            raise
        runtime.remember(organization_id, built)
        return _view(record, result, now or datetime.now(UTC), "live")

    async def _record(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        result: Verified,
        storage: MemoryStorage,
    ) -> OrganizationLicense:
        if (
            not result.valid
            or result.licence is None
            or result.customer is None
            or result.customer.id is None
            or storage.text is None
        ):
            raise LicenseKeyRejectedError(
                f"The licence does not verify on this server: {result.reason}."
            )
        licence_id = _uuid_of("licences", result.licence)
        revision = result.revision or 0
        current = await self._repository.find_current(session, organization_id)
        if current is not None and current.license_id == licence_id and revision < current.revision:
            raise LicenseDowngradeForbiddenError(
                "A licence revision older than the installed one cannot be installed."
            )
        organization = await session.get(Organization, organization_id)
        if organization is None:
            raise RuntimeError("Organisation row missing during licence install")
        customer_id = _uuid_of("customers", result.customer.id)
        if organization.customer_id is None:
            organization.customer_id = customer_id
        elif organization.customer_id != customer_id:
            raise LicenseCustomerMismatchError(
                "This licence belongs to a different commercial customer."
            )
        await self._repository.mark_superseded_now(session, organization_id)
        record = OrganizationLicense(
            id=new_uuid7(),
            organization_id=organization_id,
            license_id=licence_id,
            revision=revision,
            artifact=storage.text,
            is_current=True,
            superseded_at=None,
        )
        return await self._repository.add_record(session, record)
