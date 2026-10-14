from fastapi import APIRouter, Request

from relyxus_api.shared.http.envelope import SuccessEnvelope, wrap_success

router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get(
    "/meta",
    summary="API contract metadata",
    response_model=SuccessEnvelope[dict[str, str]],
)
def get_api_meta(request: Request) -> SuccessEnvelope[dict[str, str]]:
    app = request.app
    return wrap_success(
        {
            "service": "relyxus-api",
            "contract_version": str(app.version),
        }
    )
