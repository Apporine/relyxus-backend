import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from relyxus_api.modules.catalog.model import (
    ENVIRONMENT_PATTERN,
    LABEL_KEY_PATTERN,
    LABEL_VALUE_MAX_LENGTH,
    MAX_LABELS,
    SERVICE_DESCRIPTION_MAX_LENGTH,
    SERVICE_KEY_PATTERN,
    SERVICE_NAME_MAX_LENGTH,
    CatalogService,
    ServiceTier,
)

_LABEL_KEY = re.compile(LABEL_KEY_PATTERN)


def _check_labels(labels: dict[str, str]) -> dict[str, str]:
    if len(labels) > MAX_LABELS:
        raise ValueError(f"At most {MAX_LABELS} labels.")
    for key, value in labels.items():
        if not _LABEL_KEY.match(key):
            raise ValueError(f"Label key '{key}' must match {LABEL_KEY_PATTERN}.")
        if len(value) > LABEL_VALUE_MAX_LENGTH:
            raise ValueError(f"Label '{key}' is longer than {LABEL_VALUE_MAX_LENGTH} characters.")
    return labels


Labels = Annotated[dict[str, str], AfterValidator(_check_labels)]
ServiceName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SERVICE_NAME_MAX_LENGTH)
]
ServiceDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=SERVICE_DESCRIPTION_MAX_LENGTH)
]
Environment = Annotated[str, StringConstraints(pattern=ENVIRONMENT_PATTERN)]


class CreateServiceRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[str, StringConstraints(pattern=SERVICE_KEY_PATTERN)] = Field(
        description="Stable identifier, unique in the workspace.", examples=["card-gateway"]
    )
    name: ServiceName = Field(examples=["Card gateway"])
    description: ServiceDescription | None = None
    tier: ServiceTier = Field(examples=[ServiceTier.TIER_1])
    environment: Environment = Field(examples=["production"])
    owner_team_id: uuid.UUID | None = Field(default=None, description="A team of this workspace.")
    labels: Labels = Field(default_factory=dict, examples=[{"region": "eu-west-1"}])


class UpdateServiceRequest(BaseModel):
    """Partial update. The key never changes. Send `owner_team_id` or `description` as
    null to clear them; `labels` replaces the whole set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: ServiceName | None = None
    description: ServiceDescription | None = None
    tier: ServiceTier | None = None
    environment: Environment | None = None
    owner_team_id: uuid.UUID | None = None
    labels: Labels | None = None
    is_archived: bool | None = Field(
        default=None, description="Archive (true) or restore (false); values are kept."
    )


class ServiceView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    key: str
    name: str
    description: str | None
    tier: ServiceTier
    environment: str
    owner_team_id: uuid.UUID | None
    labels: dict[str, str]
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_service(cls, service: CatalogService) -> "ServiceView":
        return cls(
            id=service.id,
            workspace_id=service.workspace_id,
            key=service.key,
            name=service.name,
            description=service.description,
            tier=ServiceTier(service.tier),
            environment=service.environment,
            owner_team_id=service.owner_team_id,
            labels=dict(service.labels),
            archived_at=service.archived_at,
            created_at=service.created_at,
            updated_at=service.updated_at,
        )
