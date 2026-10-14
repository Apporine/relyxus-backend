"""Runtime configuration, loaded and validated once at startup (context.md §11).

Every value comes from `RELYXUS_*` environment variables. A missing or invalid required
value raises immediately so a misconfigured instance never starts serving traffic.
"""

from enum import StrEnum

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RELYXUS_", extra="forbid", frozen=True)

    environment: Environment
    public_base_url: AnyHttpUrl

    @property
    def is_api_docs_enabled(self) -> bool:
        """Swagger UI and the raw spec are never public in production (context.md §6)."""
        return self.environment is not Environment.PRODUCTION


def load_settings() -> Settings:
    # Values are read from the environment by pydantic-settings, not passed in.
    return Settings()
