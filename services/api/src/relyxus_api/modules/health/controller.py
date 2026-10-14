from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import PlainTextResponse

from relyxus_api.modules.health.metrics import render_prometheus_metrics
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


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Text exposition format for scraping (not JSON).",
    response_class=PlainTextResponse,
)
async def get_metrics(
    request: Request,
    health_service: HealthServiceDependency,
) -> PlainTextResponse:
    report = await health_service.get_readiness()
    body = render_prometheus_metrics(
        api_version=request.app.version,
        readiness=report.status,
    )
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")
