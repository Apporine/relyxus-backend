from pydantic import BaseModel, ConfigDict, Field


class PolicyEngineStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: str = Field(examples=["stub"])
    bundle_configured: bool
    bundle_path: str | None = None
