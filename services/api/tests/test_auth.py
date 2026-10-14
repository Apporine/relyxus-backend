import base64
import hashlib
import hmac
import json
import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from api_test_support import (
    TEST_OIDC_AUDIENCE,
    TEST_OIDC_ISSUER,
    bind_token_only_identity,
    make_settings,
)
from relyxus_api.app import create_app
from relyxus_api.shared.auth.access_token import (
    AccessTokenVerifier,
    InvalidAccessTokenError,
    JwksSigningKeyResolver,
)

SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KEY_ID = "test-key-1"


class StaticKeyResolver:
    def get_signing_key(self, token: str) -> object:
        return SIGNING_KEY.public_key()


def _claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": TEST_OIDC_ISSUER,
        "aud": TEST_OIDC_AUDIENCE,
        "sub": "5c2f6b1e-0d4a-4f8e-9a7b-3c1d2e4f5a6b",
        "iat": now,
        "exp": now + 300,
        "auth_time": now - 60,
        "email": "sre.lead@bank.example",
        "name": "Amira Haddad",
    }
    claims.update(overrides)
    return {key: value for key, value in claims.items() if value is not None}


def _token(claims: dict[str, Any] | None = None, key: Any = SIGNING_KEY, **headers: Any) -> str:
    return jwt.encode(
        claims or _claims(), key, algorithm="RS256", headers={"kid": KEY_ID, **headers}
    )


def _verifier(resolver: Any = None) -> AccessTokenVerifier:
    return AccessTokenVerifier(
        key_resolver=resolver or StaticKeyResolver(),
        issuer=TEST_OIDC_ISSUER,
        audience=TEST_OIDC_AUDIENCE,
        allowed_algorithms=("RS256",),
        clock_leeway_seconds=30,
    )


@pytest.fixture
def client() -> TestClient:
    app = create_app(make_settings())
    bind_token_only_identity(app)
    app.state.access_token_verifier = _verifier()
    return TestClient(app)


def _get_me(client: TestClient, token: str) -> Any:
    return client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})


def test_valid_token_returns_the_verified_identity(client: TestClient) -> None:
    response = _get_me(client, _token())

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["issuer"] == TEST_OIDC_ISSUER
    assert data["subject"] == "5c2f6b1e-0d4a-4f8e-9a7b-3c1d2e4f5a6b"
    assert data["email"] == "sre.lead@bank.example"
    assert data["authenticated_at"] is not None
    assert data["is_provisioned"] is False


def test_missing_token_is_401_with_bearer_challenge(client: TestClient) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"
    assert response.headers["www-authenticate"] == 'Bearer realm="relyxus"'


def _sign_none(claims: dict[str, Any]) -> str:
    return jwt.encode(claims, "", algorithm="none")


def _sign_hs256_with_public_key(claims: dict[str, Any]) -> str:
    # Algorithm-confusion attack: an HMAC token whose secret is the public RSA key.
    public_pem = SIGNING_KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    header = {"alg": "HS256", "typ": "JWT"}

    def encode(part: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=").decode()

    signing_input = f"{encode(header)}.{encode(claims)}"
    signature = hmac.new(public_pem, signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


@pytest.mark.parametrize(
    ("token", "reason"),
    [
        (_token(key=OTHER_KEY), "signed by another key"),
        (_token(_claims(iss="https://attacker.example/realms/relyxus")), "wrong issuer"),
        (_token(_claims(aud="another-client")), "wrong audience"),
        (_token(_claims(exp=int(time.time()) - 120)), "expired beyond leeway"),
        (_token(_claims(nbf=int(time.time()) + 600)), "not valid yet"),
        (_token(_claims(sub=None)), "missing subject"),
        (_token(_claims(exp=None)), "missing expiry"),
        (_sign_none(_claims()), "unsigned alg none"),
        (_sign_hs256_with_public_key(_claims()), "HS256 algorithm confusion"),
        ("not-a-jwt", "malformed"),
    ],
)
def test_untrustworthy_tokens_are_rejected(client: TestClient, token: str, reason: str) -> None:
    response = _get_me(client, token)

    assert response.status_code == 401, reason
    assert response.json()["code"] == "INVALID_ACCESS_TOKEN"
    assert response.json()["detail"] == "The access token is invalid or expired."
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


def test_clock_leeway_accepts_slightly_expired_token(client: TestClient) -> None:
    assert _get_me(client, _token(_claims(exp=int(time.time()) - 10))).status_code == 200


def test_jwks_resolver_selects_key_by_kid(monkeypatch: pytest.MonkeyPatch) -> None:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(SIGNING_KEY.public_key()))
    jwks = {"keys": [{**jwk, "kid": KEY_ID, "use": "sig", "alg": "RS256"}]}
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda _self: jwks)
    verifier = _verifier(JwksSigningKeyResolver("https://id.example.test/certs"))

    assert verifier.verify(_token()).subject == "5c2f6b1e-0d4a-4f8e-9a7b-3c1d2e4f5a6b"
    with pytest.raises(InvalidAccessTokenError):
        verifier.verify(_token(kid="unknown-key"))


def test_identity_endpoint_declares_bearer_security(client: TestClient) -> None:
    spec = client.get("/docs.json").json()

    assert spec["components"]["securitySchemes"]["bearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    assert spec["paths"]["/api/v1/me"]["get"]["security"] == [{"bearerAuth": []}]
