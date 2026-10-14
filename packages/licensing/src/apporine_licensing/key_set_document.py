"""Trusted key-set document v1: the file form of a `TrustedKeySet` (ADR-0002 §5.1).

Plain `.pem` files carry no key ID, environment or signing window, so the CLI and the
runtime load keys from this versioned, schema-validated document instead. It holds public
keys only; private key material is refused by `load_trusted_key` (MP-14.01).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from apporine_licensing.canonical_json import load_strict_json
from apporine_licensing.envelope import KEY_ID_PATTERN
from apporine_licensing.errors import CanonicalJsonError, KeySetConfigurationError
from apporine_licensing.key_set import (
    KeyEnvironment,
    SignatureAlgorithm,
    TrustedKeySet,
    load_trusted_key,
)
from apporine_licensing.payload import UtcTimestamp
from apporine_licensing.validation_messages import summarize_validation_error


class TrustedKeyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    key_id: Annotated[str, Field(pattern=KEY_ID_PATTERN)]
    environment: Annotated[KeyEnvironment, Field(strict=False)]
    algorithm: Annotated[SignatureAlgorithm, Field(strict=False)]
    valid_from: UtcTimestamp
    valid_until: UtcTimestamp | None = None
    public_key_pem: Annotated[str, Field(min_length=1)]


class TrustedKeySetDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, title="TrustedKeySetV1")

    key_set_version: Literal[1]
    keys: Annotated[list[TrustedKeyEntry], Field(min_length=1)]


def load_key_set_document(document: bytes) -> TrustedKeySet:
    """Parse and validate a key-set file; any problem is a configuration error."""
    try:
        parsed = load_strict_json(document)
        validated = TrustedKeySetDocument.model_validate(parsed)
    except CanonicalJsonError as error:
        raise KeySetConfigurationError(f"Key set is not valid JSON: {error}") from error
    except ValidationError as error:
        raise KeySetConfigurationError(summarize_validation_error(error)) from error
    return TrustedKeySet(
        load_trusted_key(
            key_id=entry.key_id,
            environment=entry.environment,
            public_key_pem=entry.public_key_pem.encode("ascii", errors="replace"),
            valid_from=entry.valid_from,
            valid_until=entry.valid_until,
        )
        for entry in validated.keys
    )
