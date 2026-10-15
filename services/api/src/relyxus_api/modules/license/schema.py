import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InstallLicenseRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact: str = Field(description="Signed relyxus.license JSON document")


class LicenseStatusView(BaseModel):
    model_config = ConfigDict(frozen=True)

    license_id: uuid.UUID
    revision: int
    state: str
    expires_at: datetime
    grace_ends_at: datetime
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
