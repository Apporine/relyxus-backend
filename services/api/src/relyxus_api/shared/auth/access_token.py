"""OIDC access-token verification (ADR-0003 §7; MPS-14.10, TSD-9.01, context.md §10).

Authentication happens here, at the edge. Authorisation (what this identity may do) is
decided in the service layer and by OPA, never from token contents alone.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, Protocol

import jwt

from relyxus_api.shared.errors.app_errors import AuthenticationRequiredError

_REQUIRED_CLAIMS = ("exp", "iat", "iss", "aud", "sub")


class InvalidAccessTokenError(AuthenticationRequiredError):
    code: ClassVar[str] = "INVALID_ACCESS_TOKEN"
    title: ClassVar[str] = "Invalid access token"
    bearer_error: ClassVar[str | None] = "invalid_token"


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """A verified identity. `issuer` + `subject` is the stable key; email may change."""

    issuer: str
    subject: str
    email: str | None
    display_name: str | None
    authenticated_at: datetime | None


class SigningKeyResolver(Protocol):
    def get_signing_key(self, token: str) -> object:
        """Return the verification key for this token's `kid`; raise jwt.PyJWTError if none."""
        ...


class JwksSigningKeyResolver:
    """Fetches and caches the issuer's JWKS. Reaches only the configured issuer, so it works
    unchanged with an in-cluster Keycloak in self-hosted and air-gapped deployments."""

    def __init__(self, jwks_url: str) -> None:
        self._client = jwt.PyJWKClient(jwks_url, cache_keys=True)

    def get_signing_key(self, token: str) -> object:
        return self._client.get_signing_key_from_jwt(token).key


@dataclass(frozen=True, slots=True)
class AccessTokenVerifier:
    key_resolver: SigningKeyResolver
    issuer: str
    audience: str
    allowed_algorithms: tuple[str, ...]
    clock_leeway_seconds: int

    def verify(self, token: str) -> AuthenticatedPrincipal:
        try:
            claims = jwt.decode(
                token,
                key=self.key_resolver.get_signing_key(token),  # type: ignore[arg-type]
                algorithms=list(self.allowed_algorithms),
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.clock_leeway_seconds,
                options={"require": list(_REQUIRED_CLAIMS)},
            )
        except jwt.PyJWTError as error:
            # The reason stays in the log context; clients get one generic message so the
            # response never helps an attacker tune a forged token.
            raise InvalidAccessTokenError("The access token is invalid or expired.") from error
        return AuthenticatedPrincipal(
            issuer=claims["iss"],
            subject=claims["sub"],
            email=claims.get("email"),
            display_name=claims.get("name"),
            authenticated_at=(
                datetime.fromtimestamp(claims["auth_time"], UTC) if "auth_time" in claims else None
            ),
        )
