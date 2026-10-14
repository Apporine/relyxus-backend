"""Weak ETags and If-Match on GET /workspaces/current (ADR-0003 §5)."""

import pytest
from fastapi.testclient import TestClient

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.modules.access.dependencies import WORKSPACE_HEADER
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import WORKSPACE_A1, principal_for, seed_two_organisations_with_members

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url() -> str:
    url = require_test_database_url()
    migrate_and_reset(url)
    run_as_superuser(url, seed_two_organisations_with_members)
    return url


class _SubjectTokenVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return principal_for(token)


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_app(make_settings(database_url=database_url))
    app.state.access_token_verifier = _SubjectTokenVerifier()
    return TestClient(app)


def _auth() -> dict[str, str]:
    return {
        "Authorization": "Bearer sub-amira",
        WORKSPACE_HEADER: str(WORKSPACE_A1),
    }


def test_current_workspace_returns_weak_etag(client: TestClient) -> None:
    response = client.get("/api/v1/workspaces/current", headers=_auth())

    assert response.status_code == 200
    assert response.headers["ETag"].startswith('W/"')


def test_if_match_mismatch_returns_412(client: TestClient) -> None:
    headers = {**_auth(), "If-Match": 'W/"stale"'}
    response = client.get("/api/v1/workspaces/current", headers=headers)

    assert response.status_code == 412
    assert response.json()["code"] == "PRECONDITION_FAILED"
