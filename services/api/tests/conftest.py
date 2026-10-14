from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from pydantic import AnyHttpUrl

from relyxus_api.app import create_app
from relyxus_api.shared.config.settings import Environment, Settings

type ClientFactory = Callable[[Environment], TestClient]


def make_settings(environment: Environment = Environment.LOCAL) -> Settings:
    return Settings(environment=environment, public_base_url=AnyHttpUrl("https://api.example.test"))


@pytest.fixture
def client_for() -> ClientFactory:
    def build_client(environment: Environment) -> TestClient:
        return TestClient(create_app(make_settings(environment)))

    return build_client


@pytest.fixture
def client(client_for: ClientFactory) -> TestClient:
    return client_for(Environment.LOCAL)
