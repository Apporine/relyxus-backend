from fastapi import APIRouter

from relyxus_api.modules.identity.schema import CurrentIdentity
from relyxus_api.shared.auth.dependencies import AuthenticatedPrincipalDependency
from relyxus_api.shared.http.envelope import SuccessEnvelope, wrap_success

IDENTITY_TAG = "identity"

router = APIRouter(prefix="/api/v1", tags=[IDENTITY_TAG])


@router.get(
    "/me",
    summary="Current identity",
    description="The verified identity behind the access token. Requires a Bearer token.",
    response_model=SuccessEnvelope[CurrentIdentity],
)
def get_current_identity(
    principal: AuthenticatedPrincipalDependency,
) -> SuccessEnvelope[CurrentIdentity]:
    return wrap_success(
        CurrentIdentity(
            issuer=principal.issuer,
            subject=principal.subject,
            email=principal.email,
            display_name=principal.display_name,
            authenticated_at=principal.authenticated_at,
        )
    )
