"""FastAPI dependency that authenticates every protected request (context.md §10).

Declared as a plain function so FastAPI runs it in a worker thread: the first JWKS fetch is
blocking network I/O and must not stall the event loop.
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from relyxus_api.shared.auth.access_token import AccessTokenVerifier, AuthenticatedPrincipal
from relyxus_api.shared.errors.app_errors import AuthenticationRequiredError

BEARER_SCHEME_NAME = "bearerAuth"
_bearer = HTTPBearer(scheme_name=BEARER_SCHEME_NAME, bearerFormat="JWT", auto_error=False)


def get_authenticated_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthenticatedPrincipal:
    if credentials is None:
        raise AuthenticationRequiredError("Sign in and send the access token as a Bearer token.")
    verifier: AccessTokenVerifier = request.app.state.access_token_verifier
    return verifier.verify(credentials.credentials)


AuthenticatedPrincipalDependency = Annotated[
    AuthenticatedPrincipal, Depends(get_authenticated_principal)
]
