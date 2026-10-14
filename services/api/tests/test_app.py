from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from relyxus_api.openapi_export import OPENAPI_FILE_NAME, render_openapi
from relyxus_api.shared.config.settings import Environment, load_settings

type ClientFactory = Callable[[Environment], TestClient]

OPENAPI_DIRECTORY = Path(__file__).resolve().parents[3] / "packages" / "schemas" / "openapi"


@pytest.mark.parametrize("environment", [Environment.LOCAL, Environment.STAGING])
def test_docs_are_served_outside_production(
    client_for: ClientFactory, environment: Environment
) -> None:
    client = client_for(environment)

    assert client.get("/docs").status_code == 200
    assert client.get("/docs.json").json()["info"]["title"] == "Relyxus API"


def test_docs_are_never_public_in_production(client_for: ClientFactory) -> None:
    client = client_for(Environment.PRODUCTION)

    assert client.get("/docs").status_code == 404
    assert client.get("/docs.json").status_code == 404
    assert client.get("/health").status_code == 200


def test_cors_preflight_is_allowed_outside_production(client_for: ClientFactory) -> None:
    client = client_for(Environment.LOCAL)
    response = client.options(
        "/api/v1/meta",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_cors_preflight_is_not_opened_in_production(client_for: ClientFactory) -> None:
    client = client_for(Environment.PRODUCTION)
    response = client.options(
        "/api/v1/meta",
        headers={
            "Origin": "http://example.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 405


def test_spec_lists_the_environment_server(client_for: ClientFactory) -> None:
    servers = client_for(Environment.STAGING).get("/docs.json").json()["servers"]

    assert servers == [{"url": "https://api.example.test/", "description": "staging"}]


def test_missing_required_configuration_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RELYXUS_ENVIRONMENT", raising=False)
    monkeypatch.delenv("RELYXUS_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("RELYXUS_DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        load_settings()


def test_invalid_configuration_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELYXUS_ENVIRONMENT", "prod")
    monkeypatch.setenv("RELYXUS_PUBLIC_BASE_URL", "not a url")

    with pytest.raises(ValidationError):
        load_settings()


def test_configuration_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RELYXUS_ENVIRONMENT", "staging")
    monkeypatch.setenv("RELYXUS_PUBLIC_BASE_URL", "https://api.staging.example.test")
    monkeypatch.setenv("RELYXUS_DATABASE_URL", "postgresql+psycopg://app@db.internal/relyxus")
    monkeypatch.setenv("RELYXUS_OIDC_ISSUER_URL", "https://id.example.test/realms/relyxus")
    monkeypatch.setenv("RELYXUS_OIDC_AUDIENCE", "relyxus-api")

    settings = load_settings()

    assert settings.environment is Environment.STAGING
    assert settings.is_api_docs_enabled


def test_committed_openapi_contract_matches_the_app() -> None:
    committed = (OPENAPI_DIRECTORY / OPENAPI_FILE_NAME).read_text(encoding="utf-8")

    assert committed == render_openapi(), (
        "OpenAPI contract is stale; regenerate with "
        "`uv run python -m relyxus_api.openapi_export packages/schemas/openapi`"
    )
