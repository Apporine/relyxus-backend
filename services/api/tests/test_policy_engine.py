from fastapi.testclient import TestClient

from api_test_support import bind_token_only_identity, make_settings
from relyxus_api.app import create_app
from relyxus_api.shared.auth.access_token import AuthenticatedPrincipal


class _AnyBearerVerifier:
    def verify(self, token: str) -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            issuer="https://id.example.test/realms/relyxus",
            subject=token,
            email=None,
            display_name=None,
            authenticated_at=None,
        )


def test_policy_engine_status_requires_auth() -> None:
    client = TestClient(create_app(make_settings()))
    assert client.get("/api/v1/policy/engine").status_code == 401


def test_policy_engine_status_stub() -> None:
    app = create_app(make_settings())
    bind_token_only_identity(app)
    app.state.access_token_verifier = _AnyBearerVerifier()
    client = TestClient(app)
    data = client.get("/api/v1/policy/engine", headers={"Authorization": "Bearer sub-test"}).json()[
        "data"
    ]

    assert data["mode"] == "stub"
    assert data["bundle_configured"] is False
