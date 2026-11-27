from datetime import UTC, datetime, timedelta
from typing import Annotated, ClassVar

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from apporine_licensing.connected_refresh import ConnectedRefreshPolicy
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER, WorkspaceSessionDependency
from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.idempotency.service import IdempotencyReplay, IdempotencyService
from relyxus_api.modules.license.provider import (
    AnyLicenseRuntime,
    license_status,
)
from relyxus_api.modules.license.provider import (
    install_license as install_for_runtime,
)
from relyxus_api.modules.license.schema import InstallLicenseRequest, LicenseStatusView
from relyxus_api.modules.license.service import ConnectedRefreshConfig
from relyxus_api.shared.errors.app_errors import PermissionDeniedError
from relyxus_api.shared.http.envelope import SuccessEnvelope, wrap_success

LICENSE_TAG = "license"

router = APIRouter(prefix="/api/v1", tags=[LICENSE_TAG])

_LICENSE_INSTALL_ROLES = frozenset({WorkspaceRole.ADMIN, WorkspaceRole.OWNER})


class LicenseInstallForbiddenError(PermissionDeniedError):
    code: ClassVar[str] = "LICENSE_INSTALL_FORBIDDEN"


def _runtime(request: Request) -> AnyLicenseRuntime:
    return getattr(request.app.state, "license_runtime", None)


def _connected_refresh(request: Request) -> ConnectedRefreshConfig | None:
    settings = request.app.state.settings
    if settings.license_status_url is None:
        return None
    return ConnectedRefreshConfig(
        status_url=str(settings.license_status_url),
        fetch_timeout_seconds=settings.license_status_fetch_timeout_seconds,
        policy=ConnectedRefreshPolicy(
            cache_ttl=timedelta(seconds=settings.license_status_cache_ttl_seconds),
            outage_grace=timedelta(seconds=settings.license_status_outage_grace_seconds),
        ),
        cache=request.app.state.license_status_cache,
    )


@router.get(
    "/license/status",
    summary="Current organisation licence status",
    description=f"Uses `{WORKSPACE_HEADER}` to resolve the organisation scope.",
    response_model=SuccessEnvelope[LicenseStatusView],
)
async def get_license_status(
    request: Request,
    workspace: WorkspaceSessionDependency,
) -> SuccessEnvelope[LicenseStatusView]:
    status = await license_status(
        workspace.session,
        workspace.access.organization_id,
        _runtime(request),
        connected=_connected_refresh(request),
    )
    return wrap_success(status)


@router.post(
    "/license/install",
    summary="Install or replace the organisation licence",
    status_code=201,
    response_model=SuccessEnvelope[LicenseStatusView],
)
async def install_license(
    request: Request,
    workspace: WorkspaceSessionDependency,
    body: InstallLicenseRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> JSONResponse:
    if not _LICENSE_INSTALL_ROLES.intersection(workspace.access.roles):
        raise LicenseInstallForbiddenError("Only workspace admins may install licences.")

    idempotency = IdempotencyService()
    reservation = await idempotency.begin(
        workspace.session,
        organization_id=workspace.access.organization_id,
        idempotency_key=idempotency_key,
        method=request.method,
        path=request.url.path,
        payload=body.model_dump(mode="json"),
    )
    if isinstance(reservation, IdempotencyReplay):
        return JSONResponse(status_code=reservation.status_code, content=reservation.body)

    status = await install_for_runtime(
        workspace.session,
        workspace.access.organization_id,
        body,
        _runtime(request),
        datetime.now(UTC),
        actor=workspace.access,
    )
    envelope = wrap_success(status)
    payload = envelope.model_dump(mode="json")
    await idempotency.complete(
        workspace.session,
        reservation.record_id,
        status_code=201,
        body=payload,
    )
    return JSONResponse(status_code=201, content=payload)
