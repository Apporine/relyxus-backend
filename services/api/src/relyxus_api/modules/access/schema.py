import uuid

from pydantic import BaseModel, ConfigDict, Field

from relyxus_api.modules.access.model import WorkspaceRole
from relyxus_api.modules.access.repository import WorkspaceListing


class WorkspaceSummary(BaseModel):
    """A workspace the caller can open, with the roles they hold there."""

    model_config = ConfigDict(frozen=True)

    workspace_id: uuid.UUID = Field(examples=["0192f0c4-7d1e-7a3b-9c2d-5e6f7a8b9c0d"])
    workspace_key: str = Field(examples=["payments-eu"])
    workspace_name: str = Field(examples=["Payments EU"])
    data_residency_region: str = Field(examples=["eu-west-2"])
    organization_id: uuid.UUID = Field(examples=["0192f0c4-0000-7000-8000-000000000001"])
    organization_name: str = Field(examples=["Alpha Bank"])
    roles: list[WorkspaceRole] = Field(examples=[["incident_commander", "responder"]])

    @classmethod
    def from_listing(cls, listing: WorkspaceListing) -> "WorkspaceSummary":
        return cls(
            workspace_id=listing.workspace_id,
            workspace_key=listing.workspace_key,
            workspace_name=listing.workspace_name,
            data_residency_region=listing.data_residency_region,
            organization_id=listing.organization_id,
            organization_name=listing.organization_name,
            roles=[WorkspaceRole(role) for role in listing.roles],
        )
