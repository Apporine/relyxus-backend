"""Application factory. Run with: `uvicorn --factory relyxus_api.app:build_app`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI

from relyxus_api.modules.health.controller import router as health_router
from relyxus_api.modules.health.service import DependencyProbe, HealthService
from relyxus_api.shared.config.settings import Settings, load_settings
from relyxus_api.shared.db.engine import (
    create_database_engine,
    create_session_factory,
    is_database_reachable,
)
from relyxus_api.shared.errors.handlers import register_exception_handlers
from relyxus_api.shared.errors.problem_details import PROBLEM_RESPONSES
from relyxus_api.shared.middleware.correlation_id import CorrelationIdMiddleware
from relyxus_api.shared.observability.logging import (
    configure_logging,
    install_correlation_record_factory,
)

API_TITLE = "Relyxus API"
# Bump on every contract change (context.md §6).
API_CONTRACT_VERSION = "0.2.0"
DATABASE_PROBE_NAME = "postgresql"
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
    app.state.health_service = HealthService(
        probes=[
            DependencyProbe(
                DATABASE_PROBE_NAME,
                partial(
                    is_database_reachable,
                    database_engine,
                    settings.database_probe_timeout_seconds,
                ),
            )
        ]
    )
    app.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router, responses=PROBLEM_RESPONSES)
    return app


def build_app() -> FastAPI:
    configure_logging()
    return create_app(load_settings())
