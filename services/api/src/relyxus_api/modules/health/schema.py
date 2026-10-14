from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class HealthStatus(StrEnum):
    OK = "ok"


class ReadinessStatus(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"


class LivenessReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: HealthStatus = Field(examples=[HealthStatus.OK])


class DependencyCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(examples=["postgresql"])
    is_reachable: bool = Field(examples=[True])


class ReadinessReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ReadinessStatus = Field(examples=[ReadinessStatus.READY])
    checks: list[DependencyCheck] = Field(examples=[[{"name": "postgresql", "is_reachable": True}]])
