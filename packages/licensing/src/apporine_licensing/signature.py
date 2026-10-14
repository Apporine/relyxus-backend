"""Authenticate a licence envelope against the trusted key set (ADR-0002 §6 step 1-2)."""

from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from apporine_licensing.base64url import decode_base64url
from apporine_licensing.envelope import LicenseEnvelope
from apporine_licensing.errors import (
    SignatureInvalidError,
    SigningKeyEnvironmentError,
    UnknownSigningKeyError,
    UnsupportedAlgorithmError,
)
from apporine_licensing.key_set import KeyEnvironment, SignatureAlgorithm, TrustedKey, TrustedKeySet


@dataclass(frozen=True, slots=True)
class AuthenticatedPayload:
    """Payload bytes proven to be signed by `signing_key`. Not yet schema-checked."""

    payload_bytes: bytes
    signing_key: TrustedKey


def authenticate_envelope(
    envelope: LicenseEnvelope,
    key_set: TrustedKeySet,
    expected_environment: KeyEnvironment,
) -> AuthenticatedPayload:
    """Verify the signature over the exact payload bytes; fail closed on any doubt."""
    if envelope.algorithm not in SignatureAlgorithm:
        raise UnsupportedAlgorithmError("Licence signature algorithm is not supported")
    signing_key = key_set.find(envelope.key_id)
    if signing_key is None:
        raise UnknownSigningKeyError("Licence is signed by a key this installation does not trust")
    if signing_key.environment is not expected_environment:
        raise SigningKeyEnvironmentError(
            "Licence is signed by a key from a different issuing environment"
        )
    if signing_key.algorithm != envelope.algorithm:
        raise UnsupportedAlgorithmError("Licence algorithm does not match its signing key")

    payload_bytes = decode_base64url(envelope.payload)
    signature = decode_base64url(envelope.signature)
    try:
        signing_key.public_key.verify(signature, payload_bytes, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as error:
        raise SignatureInvalidError("Licence signature does not match its payload") from error
    return AuthenticatedPayload(payload_bytes=payload_bytes, signing_key=signing_key)
