"""Licence payload schema v1 (ADR-0002 §4, LIC-5.02)."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    ValidationError,
    WithJsonSchema,
    model_validator,
)

from apporine_licensing.canonical_json import MAX_SAFE_INTEGER, canonicalize, load_strict_json
from apporine_licensing.errors import (
    CanonicalJsonError,
    LicenseMalformedError,
    LicensePayloadInvalidError,
    NonCanonicalPayloadError,
    UnsupportedSchemaVersionError,
)
from apporine_licensing.validation_messages import summarize_validation_error

SUPPORTED_SCHEMA_VERSIONS = frozenset({1})

UTC_TIMESTAMP_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
UTC_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
SLUG_PATTERN = r"^[a-z][a-z0-9-]{0,62}$"
DEPLOYMENT_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,62}$"
NAMESPACED_KEY_PATTERN = r"^[a-z][a-z0-9-]{0,62}\.[a-z][a-z0-9_]{0,62}$"


def _parse_utc_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp must be a string")
    if datetime.fromisoformat(value).strftime(UTC_TIMESTAMP_FORMAT) != value:
        raise ValueError("timestamp must be UTC in the form YYYY-MM-DDTHH:MM:SSZ")
    return datetime.fromisoformat(value).astimezone(UTC)


UtcTimestamp = Annotated[
    datetime,
    BeforeValidator(_parse_utc_timestamp),
    PlainSerializer(lambda moment: moment.strftime(UTC_TIMESTAMP_FORMAT), return_type=str),
    WithJsonSchema({"type": "string", "format": "date-time", "pattern": UTC_TIMESTAMP_PATTERN}),
]
LowercaseUuid = Annotated[str, Field(pattern=UUID_PATTERN)]
Slug = Annotated[str, Field(pattern=SLUG_PATTERN)]
NamespacedKey = Annotated[str, Field(pattern=NAMESPACED_KEY_PATTERN)]
SafeNonNegativeInteger = Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
# Enum fields validate laxly so JSON strings map to members; values outside the enum still fail.


class DeploymentAllowance(StrEnum):
    PRODUCTION = "production"
    NON_PRODUCTION = "non_production"
    DISASTER_RECOVERY = "disaster_recovery"


class SupportTier(StrEnum):
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class DeploymentBinding(BaseModel):
    """A logical deployment the licence is valid for; never a pod or container ID (LIC-12.01)."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    deployment_id: Annotated[str, Field(pattern=DEPLOYMENT_ID_PATTERN)]
    allowance: Annotated[DeploymentAllowance, Field(strict=False)]


class LicensePayload(BaseModel):
    """The signed commercial entitlement. Contains no secrets by construction (LIC-5.04)."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, title="LicensePayloadV1")

    schema_version: Literal[1]
    license_id: LowercaseUuid
    revision: Annotated[int, Field(ge=1, le=MAX_SAFE_INTEGER)]
    customer_id: LowercaseUuid
    product_id: Slug
    deployment_bindings: Annotated[list[DeploymentBinding], Field(min_length=1)]
    issued_at: UtcTimestamp
    not_before: UtcTimestamp
    expires_at: UtcTimestamp
    grace_policy_id: Slug
    entitlements: list[NamespacedKey]
    limits: dict[NamespacedKey, SafeNonNegativeInteger]
    support_tier: Annotated[SupportTier, Field(strict=False)]

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if not self.issued_at <= self.expires_at:
            raise ValueError("issued_at must not be after expires_at")
        if not self.not_before < self.expires_at:
            raise ValueError("not_before must be before expires_at")
        deployment_ids = [binding.deployment_id for binding in self.deployment_bindings]
        if len(set(deployment_ids)) != len(deployment_ids):
            raise ValueError("deployment_bindings must not repeat a deployment_id")
        if self.entitlements != sorted(set(self.entitlements)):
            raise ValueError("entitlements must be sorted and unique")
        foreign_keys = [
            key
            for key in [*self.entitlements, *self.limits]
            if key.split(".", 1)[0] != self.product_id
        ]
        if foreign_keys:
            raise ValueError("entitlement and limit keys must be namespaced by product_id")
        return self

    def to_canonical_bytes(self) -> bytes:
        """The exact bytes an issuer signs for this payload (ADR-0002 §1)."""
        return canonicalize(self.model_dump(mode="json"))


def parse_payload(payload_bytes: bytes) -> LicensePayload:
    """Parse signed payload bytes, requiring canonical form and a supported schema version."""
    try:
        document = load_strict_json(payload_bytes)
        is_canonical = canonicalize(document) == payload_bytes
    except CanonicalJsonError as error:
        raise LicenseMalformedError(f"Payload is not valid licence JSON: {error}") from error
    if not is_canonical:
        raise NonCanonicalPayloadError("Payload bytes are not in canonical form")
    if not isinstance(document, dict):
        raise LicenseMalformedError("Payload must be a JSON object")
    schema_version = document.get("schema_version")
    if isinstance(schema_version, bool) or schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise UnsupportedSchemaVersionError("Payload schema_version is not supported")
    try:
        return LicensePayload.model_validate(document)
    except ValidationError as error:
        raise LicensePayloadInvalidError(summarize_validation_error(error)) from error
