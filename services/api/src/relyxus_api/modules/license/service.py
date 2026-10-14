import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from apporine_licensing.verifier import LicenseVerifier, VerifiedLicense
from relyxus_api.modules.license.model import OrganizationLicense
from relyxus_api.modules.license.repository import LicenseRepository
from relyxus_api.modules.license.schema import LicenseStatusView
from relyxus_api.shared.errors.app_errors import DependencyUnavailableError, NotFoundError
from relyxus_api.shared.utils.ids import new_uuid7


class LicenseNotConfiguredError(DependencyUnavailableError):
    code: ClassVar[str] = "LICENSE_NOT_CONFIGURED"


class NoLicenseInstalledError(NotFoundError):
    code: ClassVar[str] = "NO_LICENSE_INSTALLED"


@dataclass(frozen=True, slots=True)
class LicenseRuntime:
    verifier: LicenseVerifier


class LicenseService:
    def __init__(self, repository: LicenseRepository | None = None) -> None:
        self._repository = repository or LicenseRepository()

    def _require_runtime(self, runtime: LicenseRuntime | None) -> LicenseVerifier:
        if runtime is None:
            raise LicenseNotConfiguredError(
                "Licence verification is not configured on this instance."
            )
        return runtime.verifier

    async def status(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        runtime: LicenseRuntime | None,
        now: datetime | None = None,
    ) -> LicenseStatusView:
        record = await self._repository.find_current(session, organization_id)
        if record is None:
            raise NoLicenseInstalledError("No licence is installed for this organisation.")
        evaluated_at = now or datetime.now(UTC)
        verified = self._verify_artifact(runtime, record.artifact.encode(), evaluated_at)
        return LicenseStatusView(
            license_id=record.license_id,
            revision=record.revision,
            state=verified.state.value,
            expires_at=verified.payload.expires_at,
            evaluated_at=evaluated_at,
        )

    async def install(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        artifact: str,
        runtime: LicenseRuntime | None,
        now: datetime | None = None,
    ) -> LicenseStatusView:
        evaluated_at = now or datetime.now(UTC)
        verified = self._verify_artifact(runtime, artifact.encode(), evaluated_at)
        await self._repository.mark_superseded_now(session, organization_id)
        record = OrganizationLicense(
            id=new_uuid7(),
            organization_id=organization_id,
            license_id=uuid.UUID(str(verified.payload.license_id)),
            revision=verified.payload.revision,
            artifact=artifact,
            is_current=True,
            superseded_at=None,
        )
        await self._repository.add_record(session, record)
        return LicenseStatusView(
            license_id=record.license_id,
            revision=record.revision,
            state=verified.state.value,
            expires_at=verified.payload.expires_at,
            evaluated_at=evaluated_at,
        )

    def _verify_artifact(
        self,
        runtime: LicenseRuntime | None,
        artifact: bytes,
        now: datetime,
    ) -> VerifiedLicense:
        verifier = self._require_runtime(runtime)
        return verifier.verify(artifact, now)
