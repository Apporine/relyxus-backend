"""Signed commercial status snapshots for connected refresh (LIC-9.03, LIC-10.02).

Remote kill/suspend commands must be signed like licence artifacts; unsigned responses are
rejected. Payload carries only commercial identifiers and status — never incident data.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from apporine_licensing.canonical_json import is_canonical, load_strict_json
from apporine_licensing.envelope import parse_envelope
from apporine_licensing.errors import (
    CanonicalJsonError,
    CustomerMismatchError,
    DeploymentNotLicensedError,
    LicenseMalformedError,
    LicensePayloadInvalidError,
    ProductMismatchError,
    UnsupportedSchemaVersionError,
)
from apporine_licensing.key_set import KeyEnvironment
from apporine_licensing.payload import SUPPORTED_SCHEMA_VERSIONS, UtcTimestamp
from apporine_licensing.signature import authenticate_envelope
from apporine_licensing.validation_messages import summarize_validation_error
from apporine_licensing.verifier import InstallationIdentity, TrustedKeySet


class CommercialStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class StatusSnapshotPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, title="StatusSnapshotV1")

    schema_version: Literal[1]
    license_id: Annotated[str, Field(min_length=1)]
    revision: Annotated[int, Field(ge=1)]
    customer_id: Annotated[str, Field(min_length=1)]
    product_id: Annotated[str, Field(min_length=1)]
    deployment_id: Annotated[str, Field(min_length=1)]
    commercial_status: Annotated[CommercialStatus, Field(strict=False)]
    effective_at: UtcTimestamp


class VerifiedStatusSnapshot:
    __slots__ = ("payload", "signing_key_id")

    def __init__(self, payload: StatusSnapshotPayload, signing_key_id: str) -> None:
        self.payload = payload
        self.signing_key_id = signing_key_id


def parse_status_payload(payload_bytes: bytes) -> StatusSnapshotPayload:
    if not is_canonical(payload_bytes):
        raise LicenseMalformedError("Status snapshot payload is not canonical JSON")
    try:
        parsed = load_strict_json(payload_bytes)
    except CanonicalJsonError as error:
        raise LicenseMalformedError(f"Status snapshot payload is not valid JSON: {error}") from error
    schema_version = parsed.get("schema_version")
    if isinstance(schema_version, bool) or schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise UnsupportedSchemaVersionError("Status snapshot schema_version is not supported")
    try:
        return StatusSnapshotPayload.model_validate(parsed)
    except ValidationError as error:
        raise LicensePayloadInvalidError(summarize_validation_error(error)) from error


def verify_status_snapshot(
    document: bytes,
    key_set: TrustedKeySet,
    environment: KeyEnvironment,
    installation: InstallationIdentity,
) -> VerifiedStatusSnapshot:
    envelope = parse_envelope(document)
    authenticated = authenticate_envelope(envelope, key_set, environment)
    payload = parse_status_payload(authenticated.payload_bytes)
    _bind_installation(payload, installation)
    return VerifiedStatusSnapshot(payload=payload, signing_key_id=authenticated.signing_key.key_id)


def _bind_installation(payload: StatusSnapshotPayload, installation: InstallationIdentity) -> None:
    if payload.product_id != installation.product_id:
        raise ProductMismatchError("Status snapshot is for a different product")
    if payload.customer_id != installation.customer_id:
        raise CustomerMismatchError("Status snapshot is for a different customer")
    if payload.deployment_id != installation.deployment_id:
        raise DeploymentNotLicensedError("Status snapshot does not cover this deployment")
