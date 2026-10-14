"""Application factory. Run with: `uvicorn --factory relyxus_api.app:build_app`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from apporine_licensing.key_set import KeyEnvironment
from apporine_licensing.verifier import InstallationIdentity, LicenseVerifier
from relyxus_api.modules.access.controller import router as access_router
from relyxus_api.modules.audit.controller import router as audit_router
from relyxus_api.modules.health.controller import router as health_router
from relyxus_api.modules.health.service import DependencyProbe, HealthService
from relyxus_api.modules.identity.controller import router as identity_router
from relyxus_api.modules.license.controller import router as license_router
from relyxus_api.modules.license.key_set_loader import load_trusted_key_set_file
from relyxus_api.modules.license.service import (
    LicenseRuntime,
    LicenseService,
    NoLicenseInstalledError,
)
from relyxus_api.modules.policy.controller import router as policy_router
from relyxus_api.modules.tenancy.context import TenantContext, apply_tenant_context
from relyxus_api.shared.auth.access_token import AccessTokenVerifier, JwksSigningKeyResolver
from relyxus_api.shared.config.settings import Environment, Settings, load_settings
from relyxus_api.shared.db.engine import (
    create_database_engine,
    create_session_factory,
    is_database_reachable,
    is_row_level_security_enforced,
)
from relyxus_api.shared.errors.handlers import register_exception_handlers
from relyxus_api.shared.errors.problem_details import AUTHENTICATED_RESPONSES, PROBLEM_RESPONSES
from relyxus_api.shared.middleware.correlation_id import CorrelationIdMiddleware
from relyxus_api.shared.observability.logging import (
    configure_logging,
    install_correlation_record_factory,
)

API_TITLE = "Relyxus API"
# Bump on every contract change (context.md §6).
API_CONTRACT_VERSION = "0.5.1"
DATABASE_PROBE_NAME = "postgresql"
ROW_LEVEL_SECURITY_PROBE_NAME = "postgresql_row_level_security"
LICENSE_READINESS_PROBE_NAME = "commercial_license"
DOCS_PATH = "/docs"
OPENAPI_PATH = "/docs.json"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await app.state.database_engine.dispose()


def create_app(settings: Settings) -> FastAPI:
    install_correlation_record_factory()
    is_docs_enabled = settings.is_api_docs_enabled
    app = FastAPI(
        title=API_TITLE,
        version=API_CONTRACT_VERSION,
        docs_url=DOCS_PATH if is_docs_enabled else None,
        openapi_url=OPENAPI_PATH if is_docs_enabled else None,
        redoc_url=None,
        servers=[{"url": str(settings.public_base_url), "description": settings.environment}],
        lifespan=_lifespan,
    )
    database_engine = create_database_engine(settings)
    app.state.settings = settings
    app.state.database_engine = database_engine
    app.state.session_factory = create_session_factory(database_engine)
    app.state.access_token_verifier = AccessTokenVerifier(
        key_resolver=JwksSigningKeyResolver(settings.resolved_jwks_url),
        issuer=settings.oidc_issuer_url,
        audience=settings.oidc_audience,
        allowed_algorithms=settings.oidc_allowed_algorithms,
        clock_leeway_seconds=settings.oidc_clock_leeway_seconds,
    )
    app.state.license_runtime = _build_license_runtime(settings)
    app.state.health_service = HealthService(_build_probes(settings, database_engine, app))
    app.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router, responses=PROBLEM_RESPONSES)
    for router in (identity_router, access_router, audit_router, license_router, policy_router):
        app.include_router(router, responses=PROBLEM_RESPONSES | AUTHENTICATED_RESPONSES)
    return app


def _build_license_runtime(settings: Settings) -> LicenseRuntime | None:
    if (
        settings.license_trusted_key_set_path is None
        or settings.license_customer_id is None
        or settings.license_deployment_id is None
    ):
        return None
    key_set = load_trusted_key_set_file(Path(settings.license_trusted_key_set_path))
    verifier = LicenseVerifier(
        key_set=key_set,
        installation=InstallationIdentity(
            product_id="relyxus",
            customer_id=settings.license_customer_id,
            deployment_id=settings.license_deployment_id,
            environment=KeyEnvironment(settings.license_key_environment),
        ),
    )
    return LicenseRuntime(verifier=verifier)


def _build_probes(
    settings: Settings, database_engine: AsyncEngine, app: FastAPI
) -> list[DependencyProbe]:
    timeout = settings.database_probe_timeout_seconds
    probes = [
        DependencyProbe(
            DATABASE_PROBE_NAME, partial(is_database_reachable, database_engine, timeout)
        )
    ]
    if settings.environment is not Environment.LOCAL:
        probes.append(
            DependencyProbe(
                ROW_LEVEL_SECURITY_PROBE_NAME,
                partial(is_row_level_security_enforced, database_engine, timeout),
            )
        )
    if settings.license_readiness_organization_id is not None:
        organization_id = settings.license_readiness_organization_id

        async def commercial_license_ready() -> bool:
            runtime = app.state.license_runtime
            if runtime is None:
                return False
            session_factory = app.state.session_factory
            async with session_factory() as session, session.begin():
                await apply_tenant_context(
                    session,
                    TenantContext(organization_id=organization_id, workspace_id=None),
                )
                try:
                    view = await LicenseService().status(session, organization_id, runtime)
                except NoLicenseInstalledError:
                    return False
                return view.state in ("active", "grace")

        probes.append(DependencyProbe(LICENSE_READINESS_PROBE_NAME, commercial_license_ready))
    return probes


def build_app() -> FastAPI:
    configure_logging()
    return create_app(load_settings())
