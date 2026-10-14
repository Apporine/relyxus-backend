import asyncio

from fastapi.testclient import TestClient

from relyxus_api.modules.health.schema import ReadinessStatus
from relyxus_api.modules.health.service import DependencyProbe, HealthService


def test_liveness_returns_ok_in_success_envelope(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok"}}


def test_readiness_is_503_when_the_database_is_unreachable(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["data"] == {
        "status": "not_ready",
        "checks": [{"name": "postgresql", "is_reachable": False}],
    }


def test_readiness_is_503_when_a_dependency_is_unreachable(client: TestClient) -> None:
    async def is_unreachable() -> bool:
        return False

    client.app.state.health_service = HealthService(  # type: ignore[attr-defined]
        [DependencyProbe("postgresql", is_unreachable)]
    )

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["data"]["status"] == "not_ready"
    assert response.json()["data"]["checks"] == [{"name": "postgresql", "is_reachable": False}]


def test_service_reports_ready_only_when_all_probes_pass() -> None:
    async def passes() -> bool:
        return True

    async def fails() -> bool:
        return False

    all_pass = HealthService([DependencyProbe("a", passes), DependencyProbe("b", passes)])
    one_fails = HealthService([DependencyProbe("a", passes), DependencyProbe("b", fails)])

    assert asyncio.run(all_pass.get_readiness()).status is ReadinessStatus.READY
    assert asyncio.run(one_fails.get_readiness()).status is ReadinessStatus.NOT_READY


def test_liveness_does_not_consult_dependencies(client: TestClient) -> None:
    async def explode() -> bool:
        raise AssertionError("liveness must not check dependencies")

    client.app.state.health_service = HealthService(  # type: ignore[attr-defined]
        [DependencyProbe("postgresql", explode)]
    )

    assert client.get("/health").status_code == 200
