import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InstallLicenseRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact: str | None = Field(
        default=None, description="Signed relyxus.license JSON document (licence provider apporine)"
    )
    licence_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=64,
        description="Veryion licence key (licence provider veryion)",
    )

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.artifact is None) == (self.licence_key is None):
            raise ValueError("Send either artifact or licence_key.")
        return self


class LicenseStatusView(BaseModel):
    model_config = ConfigDict(frozen=True)

    license_id: uuid.UUID
    revision: int
    state: str
    reason: str | None = Field(
        default=None,
        description="Why the licence does not verify, when state is invalid (Veryion).",
    )
    expires_at: datetime | None
    grace_ends_at: datetime | None
    entitlements: tuple[str, ...]
    evaluated_at: datetime
    has_current: bool = True
    connected_refresh_source: str | None = Field(
        default=None,
        description=(
            "When connected refresh is configured: live fetch succeeded, "
            "or cache used after outage."
        ),
    )
