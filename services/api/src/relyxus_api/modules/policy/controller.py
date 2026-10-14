from fastapi import APIRouter, Request

from relyxus_api.modules.policy.schema import PolicyEngineStatus
from relyxus_api.shared.auth.dependencies import AuthenticatedPrincipalDependency
from relyxus_api.shared.http.envelope import SuccessEnvelope, wrap_success

POLICY_TAG = "policy"

router = APIRouter(prefix="/api/v1", tags=[POLICY_TAG])


@router.get(
    "/policy/engine",
    summary="Policy engine status",
    description="Reports whether an OPA bundle path is configured (evaluation stubbed).",
    response_model=SuccessEnvelope[PolicyEngineStatus],
)
def get_policy_engine_status(
    request: Request,
    _principal: AuthenticatedPrincipalDependency,
) -> SuccessEnvelope[PolicyEngineStatus]:
    settings = request.app.state.settings
    bundle_path = settings.policy_bundle_path
    return wrap_success(
        PolicyEngineStatus(
            mode="stub",
            bundle_configured=bundle_path is not None,
            bundle_path=bundle_path,
        )
    )
