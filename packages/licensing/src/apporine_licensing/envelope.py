"""Signed licence envelope v1 (ADR-0002 §1)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from apporine_licensing.canonical_json import load_strict_json
from apporine_licensing.errors import (
    CanonicalJsonError,
    LicenseMalformedError,
    UnsupportedEnvelopeVersionError,
)
from apporine_licensing.validation_messages import summarize_validation_error

SUPPORTED_ENVELOPE_VERSIONS = frozenset({1})

ALGORITHM_PATTERN = r"^[A-Z0-9_]{1,64}$"
KEY_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,127}$"
BASE64URL_PATTERN = r"^[A-Za-z0-9_-]+$"


class LicenseEnvelope(BaseModel):
    """Detached signature over the canonical payload bytes; unknown members are rejected."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, title="LicenseEnvelopeV1")

    envelope_version: Annotated[int, Field(ge=1)]
    algorithm: Annotated[str, Field(pattern=ALGORITHM_PATTERN)]
    key_id: Annotated[str, Field(pattern=KEY_ID_PATTERN)]
    payload: Annotated[str, Field(pattern=BASE64URL_PATTERN)]
    signature: Annotated[str, Field(pattern=BASE64URL_PATTERN)]


def parse_envelope(document: bytes) -> LicenseEnvelope:
    """Parse an artifact's bytes into an envelope of a supported version."""
    try:
        parsed = load_strict_json(document)
    except CanonicalJsonError as error:
        raise LicenseMalformedError(f"Licence file is not valid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise LicenseMalformedError("Licence file must be a JSON object")
    try:
        envelope = LicenseEnvelope.model_validate(parsed)
    except ValidationError as error:
        raise LicenseMalformedError(summarize_validation_error(error)) from error
    if envelope.envelope_version not in SUPPORTED_ENVELOPE_VERSIONS:
        raise UnsupportedEnvelopeVersionError("Licence envelope_version is not supported")
    return envelope
