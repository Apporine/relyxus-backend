import os
from collections.abc import AsyncIterator

from fastapi import FastAPI
from pydantic import AnyHttpUrl, SecretStr

from relyxus_api.modules.identity.dependencies import open_identity_session
from relyxus_api.modules.identity.service import ResolvedIdentity
from relyxus_api.shared.auth.dependencies import AuthenticatedPrincipalDependency
from relyxus_api.shared.config.settings import Environment, Settings

TEST_DATABASE_URL_VARIABLE = "RELYXUS_TEST_DATABASE_URL"
TEST_OIDC_ISSUER = "https://id.example.test/realms/relyxus"
TEST_OIDC_AUDIENCE = "relyxus-api"
# Nothing listens on port 1, so tests that do not need a database see it as unreachable.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://relyxus@127.0.0.1:1/unreachable"


def get_test_database_url() -> str | None:
    return os.environ.get(TEST_DATABASE_URL_VARIABLE)


async def token_only_identity(
    principal: AuthenticatedPrincipalDependency,
) -> AsyncIterator[ResolvedIdentity]:
    yield ResolvedIdentity(
        issuer=principal.issuer,
        subject=principal.subject,
        email=principal.email,
        display_name=principal.display_name,
        authenticated_at=principal.authenticated_at,
        is_provisioned=False,
        user_id=None,
        status=None,
    )


def bind_token_only_identity(app: FastAPI) -> None:
    app.dependency_overrides[open_identity_session] = token_only_identity


def make_settings(
    environment: Environment = Environment.LOCAL,
    database_url: str = UNREACHABLE_DATABASE_URL,
) -> Settings:
    return Settings(
        environment=environment,
        public_base_url=AnyHttpUrl("https://api.example.test"),
        database_url=SecretStr(database_url),
        database_probe_timeout_seconds=1.0,
        oidc_issuer_url=TEST_OIDC_ISSUER,
        oidc_audience=TEST_OIDC_AUDIENCE,
    )
