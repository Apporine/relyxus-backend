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
    evaluated_at: datetime
    has_current: bool = True
