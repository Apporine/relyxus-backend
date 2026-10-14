"""Application factory. Run with: `uvicorn --factory relyxus_api.app:build_app`."""

from fastapi import FastAPI

from relyxus_api.modules.health.controller import router as health_router
from relyxus_api.modules.health.service import HealthService
from relyxus_api.shared.config.settings import Settings, load_settings
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
DOCS_PATH = "/docs"
OPENAPI_PATH = "/docs.json"


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
    )
    app.state.settings = settings
    app.state.health_service = HealthService(probes=[])
    app.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router, responses=PROBLEM_RESPONSES)
    return app


def build_app() -> FastAPI:
    configure_logging()
    return create_app(load_settings())
