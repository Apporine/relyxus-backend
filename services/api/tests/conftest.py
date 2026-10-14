import asyncio
import sys
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from api_test_support import make_settings
from relyxus_api.app import create_app
from relyxus_api.shared.config.settings import Environment

type ClientFactory = Callable[[Environment], TestClient]

# psycopg's async driver cannot use Windows' default Proactor loop; production runs on Linux.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def client_for() -> ClientFactory:
    def build_client(environment: Environment) -> TestClient:
        return TestClient(create_app(make_settings(environment)))

    return build_client


@pytest.fixture
def client(client_for: ClientFactory) -> TestClient:
    return client_for(Environment.LOCAL)
