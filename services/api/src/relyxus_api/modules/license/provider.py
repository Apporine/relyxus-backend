"""Picks the licensing behind /license from the configured runtime (RELYXUS_LICENSE_PROVIDER)."""

import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.service import WorkspaceAccess
from relyxus_api.modules.audit.model import ActorType, AuditOutcome
from relyxus_api.modules.audit.service import AuditService, NewAuditEvent
from relyxus_api.modules.license.schema import InstallLicenseRequest, LicenseStatusView
from relyxus_api.modules.license.service import (
    ConnectedRefreshConfig,
    LicenseRuntime,
    LicenseService,
)
from relyxus_api.modules.license.veryion_service import VeryionLicenseRuntime, VeryionLicenseService
from relyxus_api.shared.errors.app_errors import ValidationFailedError
from relyxus_api.shared.observability.correlation import get_correlation_id

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
    actor: WorkspaceAccess | None = None,
) -> LicenseStatusView:
    view = await _install(session, organization_id, body, runtime, now)
    if actor is not None:
        # A licence install changes what the organisation may use, so it is audited
        # in the same transaction.
        await AuditService().append(
            session,
            NewAuditEvent(
                organization_id=organization_id,
                workspace_id=actor.workspace_id,
                actor_type=ActorType.USER,
                actor_user_id=actor.user_id,
                effective_user_id=None,
                action="license.installed",
                target_type="license",
                target_id=str(view.license_id),
                outcome=AuditOutcome.SUCCEEDED,
                before_state=None,
                after_state={
                    "provider": "veryion"
                    if isinstance(runtime, VeryionLicenseRuntime)
                    else "apporine",
                    "revision": view.revision,
                    "state": view.state,
                    "expires_at": view.expires_at.isoformat() if view.expires_at else None,
                },
                correlation_id=get_correlation_id(),
            ),
        )
    return view


async def _install(
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
