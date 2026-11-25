"""Picks the licensing behind /license from the configured runtime (RELYXUS_LICENSE_PROVIDER)."""

import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.license.schema import InstallLicenseRequest, LicenseStatusView
from relyxus_api.modules.license.service import (
    ConnectedRefreshConfig,
    LicenseRuntime,
    LicenseService,
)
from relyxus_api.modules.license.veryion_service import VeryionLicenseRuntime, VeryionLicenseService
from relyxus_api.shared.errors.app_errors import ValidationFailedError

AnyLicenseRuntime = LicenseRuntime | VeryionLicenseRuntime | None


class LicenseRequestMismatchError(ValidationFailedError):
    code: ClassVar[str] = "LICENSE_REQUEST_MISMATCH"


async def license_status(
    session: AsyncSession,
    organization_id: uuid.UUID,
    runtime: AnyLicenseRuntime,
    *,
    now: datetime | None = None,
    connected: ConnectedRefreshConfig | None = None,
) -> LicenseStatusView:
    if isinstance(runtime, VeryionLicenseRuntime):
        return await VeryionLicenseService().status(session, organization_id, runtime, now)
    return await LicenseService().status(session, organization_id, runtime, now, connected)


async def install_license(
    session: AsyncSession,
    organization_id: uuid.UUID,
    body: InstallLicenseRequest,
    runtime: AnyLicenseRuntime,
    now: datetime,
) -> LicenseStatusView:
    if isinstance(runtime, VeryionLicenseRuntime):
        if body.licence_key is None:
            raise LicenseRequestMismatchError(
                "This server uses Veryion licence keys. Send licence_key."
            )
        return await VeryionLicenseService().install(
            session, organization_id, body.licence_key, runtime, now
        )
    if body.artifact is None:
        raise LicenseRequestMismatchError(
            "This server uses signed licence documents. Send artifact."
        )
    return await LicenseService().install(session, organization_id, body.artifact, runtime, now)
