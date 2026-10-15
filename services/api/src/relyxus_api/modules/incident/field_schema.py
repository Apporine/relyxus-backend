import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from relyxus_api.modules.incident.field_model import (
    FIELD_DESCRIPTION_MAX_LENGTH,
    FIELD_KEY_PATTERN,
    FIELD_LABEL_MAX_LENGTH,
    MAX_OPTIONS,
    OPTION_LABEL_MAX_LENGTH,
    REQUIRABLE_STAGES,
    CustomFieldDefinition,
    FieldDataType,
)
from relyxus_api.modules.incident.field_service import DisplayCondition, FieldOption
from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.model import IncidentSeverity

FieldLabel = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=FIELD_LABEL_MAX_LENGTH)
]
FieldDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=FIELD_DESCRIPTION_MAX_LENGTH)
]


class OptionModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Annotated[str, StringConstraints(pattern="^[a-z0-9][a-z0-9_-]{0,62}$")] = Field(
        examples=["eu_west"]
    )
    label: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=OPTION_LABEL_MAX_LENGTH),
    ] = Field(examples=["EU West"])

    def to_option(self) -> FieldOption:
        return FieldOption(value=self.value, label=self.label)


class ConditionModel(BaseModel):
    """Empty lists mean "any"; when both are set, both must match."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    incident_type_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    severities: list[IncidentSeverity] = Field(default_factory=list, max_length=4)

    def to_condition(self) -> DisplayCondition:
        return DisplayCondition(
            incident_type_ids=tuple(self.incident_type_ids), severities=tuple(self.severities)
        )


Options = Annotated[list[OptionModel], Field(max_length=MAX_OPTIONS)]


def _requirable(stage: IncidentLifecycleState) -> IncidentLifecycleState:
    if stage not in REQUIRABLE_STAGES:
        names = ", ".join(requirable.value for requirable in REQUIRABLE_STAGES)
        raise ValueError(f"A field can be required at one of: {names}.")
    return stage


RequiredStage = Annotated[IncidentLifecycleState, AfterValidator(_requirable)]


class CreateCustomFieldRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[str, StringConstraints(pattern=FIELD_KEY_PATTERN)] = Field(
        description="Stable identifier; lowercase, digits, underscores.", examples=["root_region"]
    )
    label: FieldLabel = Field(examples=["Affected region"])
    description: FieldDescription | None = None
    data_type: FieldDataType = Field(
        description="Fixed once created.", examples=[FieldDataType.SINGLE_CHOICE]
    )
    options: Options = Field(default_factory=list, description="Choice fields only.")
    display_condition: ConditionModel = Field(default_factory=ConditionModel)
    required_at_stage: RequiredStage | None = Field(
        default=None,
        description="Must be filled before the incident reaches this stage (MPS-8A.04).",
        examples=[IncidentLifecycleState.RESOLVED],
    )


class UpdateCustomFieldRequest(BaseModel):
    """Partial update; key and data type never change. Each change is a new version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: FieldLabel | None = None
    description: FieldDescription | None = None
    options: Options | None = None
    display_condition: ConditionModel | None = None
    required_at_stage: RequiredStage | None = None
    is_archived: bool | None = Field(
        default=None, description="Archiving is deleting: existing values stay (MPS-8A.05)."
    )


class CustomFieldView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    key: str
    label: str
    description: str | None
    data_type: FieldDataType
    options: list[dict[str, Any]]
    display_condition: dict[str, Any]
    required_at_stage: IncidentLifecycleState | None
    version: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_field(cls, found: CustomFieldDefinition) -> "CustomFieldView":
        return cls(
            id=found.id,
            key=found.key,
            label=found.label,
            description=found.description,
            data_type=FieldDataType(found.data_type),
            options=list(found.options),
            display_condition=dict(found.display_condition),
            required_at_stage=(
                None
                if found.required_at_stage is None
                else IncidentLifecycleState(found.required_at_stage)
            ),
            version=found.version,
            archived_at=found.archived_at,
            created_at=found.created_at,
            updated_at=found.updated_at,
        )
