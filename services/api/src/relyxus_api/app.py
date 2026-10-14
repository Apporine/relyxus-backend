"""Application factory. Run with: `uvicorn --factory relyxus_api.app:build_app`."""

from fastapi import FastAPI

from relyxus_api.modules.health.controller import router as health_router
from relyxus_api.modules.health.service import HealthService
from relyxus_api.shared.config.settings import Settings, load_settings

API_TITLE = "Relyxus API"
# Bump on every contract change (context.md §6).
API_CONTRACT_VERSION = "0.1.0"
DOCS_PATH = "/docs"
OPENAPI_PATH = "/docs.json"


def create_app(settings: Settings) -> FastAPI:
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
    app.include_router(health_router)
    return app


def build_app() -> FastAPI:
    return create_app(load_settings())
