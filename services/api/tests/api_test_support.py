import os

from pydantic import AnyHttpUrl, SecretStr

from relyxus_api.shared.config.settings import Environment, Settings

TEST_DATABASE_URL_VARIABLE = "RELYXUS_TEST_DATABASE_URL"
# Nothing listens on port 1, so tests that do not need a database see it as unreachable.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://relyxus@127.0.0.1:1/unreachable"


def get_test_database_url() -> str | None:
    return os.environ.get(TEST_DATABASE_URL_VARIABLE)


def make_settings(
    environment: Environment = Environment.LOCAL,
    database_url: str = UNREACHABLE_DATABASE_URL,
) -> Settings:
    return Settings(
        environment=environment,
        public_base_url=AnyHttpUrl("https://api.example.test"),
        database_url=SecretStr(database_url),
        database_probe_timeout_seconds=1.0,
    )
