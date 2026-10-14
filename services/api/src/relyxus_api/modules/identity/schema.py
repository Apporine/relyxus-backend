from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CurrentIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    issuer: str = Field(examples=["https://id.bank.example/realms/relyxus"])
    subject: str = Field(examples=["5c2f6b1e-0d4a-4f8e-9a7b-3c1d2e4f5a6b"])
    email: str | None = Field(examples=["sre.lead@bank.example"])
    display_name: str | None = Field(examples=["Amira Haddad"])
    authenticated_at: datetime | None = Field(examples=["2026-10-14T07:56:00Z"])
