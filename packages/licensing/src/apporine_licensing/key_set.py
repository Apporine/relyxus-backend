"""Trusted public verification keys (ADR-0002 §5, LIC-6.03, LIC-6.04).

The verifier never discovers keys itself; the runtime supplies the set it trusts. Only
public key material is accepted here: a private key is rejected outright (MP-14.01).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from apporine_licensing.errors import KeySetConfigurationError


class SignatureAlgorithm(StrEnum):
    ECDSA_P256_SHA256 = "ECDSA_P256_SHA256"


class KeyEnvironment(StrEnum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"


@dataclass(frozen=True, slots=True)
class TrustedKey:
    key_id: str
    environment: KeyEnvironment
    algorithm: SignatureAlgorithm
    public_key: ec.EllipticCurvePublicKey
    valid_from: datetime
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        if self.valid_from.tzinfo is None or (
            self.valid_until is not None and self.valid_until.tzinfo is None
        ):
            raise KeySetConfigurationError(f"Key {self.key_id}: validity times must be UTC-aware")
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise KeySetConfigurationError(f"Key {self.key_id}: valid_until must follow valid_from")
        if not isinstance(self.public_key.curve, ec.SECP256R1):
            raise KeySetConfigurationError(f"Key {self.key_id}: algorithm requires a P-256 key")

    def can_have_issued_at(self, moment: datetime) -> bool:
        """Whether a licence issued at `moment` falls inside this key's signing window."""
        return self.valid_from <= moment and (
            self.valid_until is None or moment <= self.valid_until
        )


def load_trusted_key(
    *,
    key_id: str,
    environment: KeyEnvironment,
    public_key_pem: bytes,
    valid_from: datetime,
    valid_until: datetime | None = None,
) -> TrustedKey:
    """Build a trusted key from PEM-encoded public key material."""
    if b"PRIVATE KEY" in public_key_pem:
        raise KeySetConfigurationError(f"Key {key_id}: private key material is never accepted")
    try:
        public_key = load_pem_public_key(public_key_pem)
    except ValueError as error:
        raise KeySetConfigurationError(f"Key {key_id}: not a valid PEM public key") from error
    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise KeySetConfigurationError(f"Key {key_id}: algorithm requires an EC public key")
    return TrustedKey(
        key_id=key_id,
        environment=environment,
        algorithm=SignatureAlgorithm.ECDSA_P256_SHA256,
        public_key=public_key,
        valid_from=valid_from,
        valid_until=valid_until,
    )


class TrustedKeySet:
    """Keys trusted by one installation; several may coexist during rotation (MPS-29.16)."""

    def __init__(self, keys: Iterable[TrustedKey]) -> None:
        self._keys: dict[str, TrustedKey] = {}
        for key in keys:
            if key.key_id in self._keys:
                raise KeySetConfigurationError(f"Duplicate key_id in key set: {key.key_id}")
            self._keys[key.key_id] = key
        if not self._keys:
            raise KeySetConfigurationError("Trusted key set must contain at least one key")

    def find(self, key_id: str) -> TrustedKey | None:
        return self._keys.get(key_id)
