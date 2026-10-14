"""Liveness and readiness (MP-28.01, TSD §11; DEP §15: readiness reflects ability to serve)."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from relyxus_api.modules.health.schema import (
    DependencyCheck,
    HealthStatus,
    LivenessReport,
    ReadinessReport,
    ReadinessStatus,
)


@dataclass(frozen=True, slots=True)
class DependencyProbe:
    """A named reachability check for something this service needs to serve traffic."""

    name: str
    check_reachability: Callable[[], Awaitable[bool]]


class HealthService:
    def __init__(self, probes: Sequence[DependencyProbe]) -> None:
        self._probes = tuple(probes)

    def get_liveness(self) -> LivenessReport:
        # Liveness never depends on downstream systems, so a degraded dependency does not
        # cause restarts (DEP §15).
        return LivenessReport(status=HealthStatus.OK)

    async def get_readiness(self) -> ReadinessReport:
        checks = [
            DependencyCheck(name=probe.name, is_reachable=await probe.check_reachability())
            for probe in self._probes
        ]
        is_ready = all(check.is_reachable for check in checks)
        return ReadinessReport(
            status=ReadinessStatus.READY if is_ready else ReadinessStatus.NOT_READY,
            checks=checks,
        )
