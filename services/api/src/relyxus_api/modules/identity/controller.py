from fastapi import APIRouter

from relyxus_api.modules.identity.dependencies import ResolvedIdentityDependency
from relyxus_api.modules.identity.schema import CurrentIdentity
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
    identity: ResolvedIdentityDependency,
) -> SuccessEnvelope[CurrentIdentity]:
    return wrap_success(
        CurrentIdentity(
            issuer=identity.issuer,
            subject=identity.subject,
            email=identity.email,
            display_name=identity.display_name,
            authenticated_at=identity.authenticated_at,
            is_provisioned=identity.is_provisioned,
            user_id=identity.user_id,
            status=identity.status,
        )
    )
