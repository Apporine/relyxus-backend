import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from relyxus_api.modules.configuration.model import (
    ConfigurationObjectType,
    ConfigurationSource,
    ConfigurationVersion,
)


class ConfigurationVersionView(BaseModel):
    model_config = ConfigDict(frozen=True)

    object_type: ConfigurationObjectType
    object_id: uuid.UUID
    version: int = Field(description="1 for the creation, then +1 per change.")
    source: ConfigurationSource
    actor_user_id: uuid.UUID | None
    snapshot: dict[str, Any] = Field(description="The object's full state after this change.")
    difference: dict[str, Any] = Field(
        description='Changed fields as `{field: {"before": …, "after": …}}`.'
    )
    created_at: datetime

    @classmethod
    def from_version(cls, version: ConfigurationVersion) -> "ConfigurationVersionView":
        return cls(
            object_type=ConfigurationObjectType(version.object_type),
            object_id=version.object_id,
            version=version.version,
            source=ConfigurationSource(version.source),
            actor_user_id=version.actor_user_id,
            snapshot=version.snapshot,
            difference=version.difference,
            created_at=version.created_at,
        )
