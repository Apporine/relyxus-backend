from pydantic import AnyHttpUrl

from relyxus_api.shared.config.settings import Environment, Settings


def make_settings(environment: Environment = Environment.LOCAL) -> Settings:
    return Settings(environment=environment, public_base_url=AnyHttpUrl("https://api.example.test"))
