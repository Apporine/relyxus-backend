"""GET /me includes provisioned user details when the identity exists in the database."""

import pytest
from fastapi.testclient import TestClient

from api_test_support import make_settings
from db_test_support import migrate_and_reset, require_test_database_url, run_as_superuser
from relyxus_api.app import create_app
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal
from tenancy_fixtures import AMIRA, ISSUER, principal_for, seed_two_organisations_with_members

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


def test_me_returns_provisioned_user(client: TestClient) -> None:
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer sub-amira"})
    data = response.json()["data"]

    assert response.status_code == 200
    assert data["is_provisioned"] is True
    assert data["user_id"] == str(AMIRA)
    assert data["status"] == "active"
    assert data["issuer"] == ISSUER


def test_me_marks_unknown_subjects_unprovisioned(client: TestClient) -> None:
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer sub-stranger"})
    data = response.json()["data"]

    assert response.status_code == 200
    assert data["is_provisioned"] is False
    assert data["user_id"] is None
