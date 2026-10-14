from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from relyxus_api.modules.health.schema import LivenessReport, ReadinessReport, ReadinessStatus
from relyxus_api.modules.health.service import HealthService
from relyxus_api.shared.http.envelope import SuccessEnvelope, wrap_success

HEALTH_TAG = "health"

router = APIRouter(tags=[HEALTH_TAG])


def get_health_service(request: Request) -> HealthService:
    health_service: HealthService = request.app.state.health_service
    return health_service


HealthServiceDependency = Annotated[HealthService, Depends(get_health_service)]


@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns 200 while the process is running. Does not check dependencies.",
    response_model=SuccessEnvelope[LivenessReport],
)
def get_liveness(health_service: HealthServiceDependency) -> SuccessEnvelope[LivenessReport]:
    return wrap_success(health_service.get_liveness())


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Returns 200 only when every required dependency is reachable; 503 otherwise.",
    response_model=SuccessEnvelope[ReadinessReport],
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": SuccessEnvelope[ReadinessReport]}},
)
async def get_readiness(
    health_service: HealthServiceDependency, response: Response
) -> SuccessEnvelope[ReadinessReport]:
    report = await health_service.get_readiness()
    if report.status is ReadinessStatus.NOT_READY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return wrap_success(report)
