"""Runtime configuration, loaded and validated once at startup (context.md §11).

Every value comes from `RELYXUS_*` environment variables. A missing or invalid required
value raises immediately so a misconfigured instance never starts serving traffic.
"""

from enum import StrEnum

from pydantic import AnyHttpUrl, Field, NonNegativeInt, PositiveFloat, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


DATABASE_URL_SCHEME = "postgresql+psycopg://"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RELYXUS_", extra="forbid", frozen=True)

    environment: Environment
    public_base_url: AnyHttpUrl
    # Secret: contains credentials; never shown in reprs, logs or errors.
    database_url: SecretStr
    database_probe_timeout_seconds: PositiveFloat = 2.0
    # OIDC access tokens are issued by Keycloak only (ADR-0003 §7, TSD-9.01).
    # Kept as the exact string: OIDC requires `iss` to match it character for character.
    oidc_issuer_url: str
    oidc_audience: str = Field(min_length=1)
    # Defaults to Keycloak's JWKS path under the issuer when not set.
    oidc_jwks_url: AnyHttpUrl | None = None
    oidc_allowed_algorithms: tuple[str, ...] = ("RS256",)
    oidc_clock_leeway_seconds: NonNegativeInt = 30
    license_trusted_key_vector_path: str | None = None
    license_customer_id: str | None = None
    license_deployment_id: str | None = None
    license_key_environment: str = "production"

    @field_validator("database_url")
    @classmethod
    def require_psycopg_driver(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(DATABASE_URL_SCHEME):
            raise ValueError(f"must start with {DATABASE_URL_SCHEME}")
        return value

    @field_validator("oidc_issuer_url")
    @classmethod
    def require_http_issuer(cls, value: str) -> str:
        AnyHttpUrl(value)
        return value

    @property
    def resolved_jwks_url(self) -> str:
        if self.oidc_jwks_url is not None:
            return str(self.oidc_jwks_url)
        return f"{self.oidc_issuer_url.rstrip('/')}/protocol/openid-connect/certs"

    @property
    def is_api_docs_enabled(self) -> bool:
        """Swagger UI and the raw spec are never public in production (context.md §6)."""
        return self.environment is not Environment.PRODUCTION


def load_settings() -> Settings:
    # Values are read from the environment by pydantic-settings, not passed in.
    return Settings()
