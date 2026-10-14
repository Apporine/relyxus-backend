"""Test-only licence signing. Keys are generated per test session and never stored.

The real issuer signs with a non-exportable AWS KMS key in the Apporine Control Plane
(LIC-6.01); no private key is ever stored in this repository (MP-14.01).
"""

from datetime import UTC, datetime

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from apporine_licensing.base64url import encode_base64url
from apporine_licensing.canonical_json import canonicalize
from apporine_licensing.key_set import KeyEnvironment, SignatureAlgorithm, TrustedKey

CUSTOMER_ID = "6f1c3a52-2d4e-4b7a-9c1e-3f5a7b9d0e21"
LICENSE_ID = "0b7e2f64-81c9-4d3a-a5f2-9e4c6d8b1a37"
DEPLOYMENT_ID = "acme-bank-prod-eu"
PRODUCTION_KEY_ID = "apporine-license-test-prod-1"
KEY_VALID_FROM = datetime(2026, 1, 1, tzinfo=UTC)


def sign_envelope(
    payload_bytes: bytes, private_key: ec.EllipticCurvePrivateKey, key_id: str
) -> bytes:
    """Build envelope bytes exactly as the issuer would (ADR-0002 §1)."""
    signature = private_key.sign(payload_bytes, ec.ECDSA(hashes.SHA256()))
    return canonicalize(
        {
            "envelope_version": 1,
            "algorithm": SignatureAlgorithm.ECDSA_P256_SHA256.value,
            "key_id": key_id,
            "payload": encode_base64url(payload_bytes),
            "signature": encode_base64url(signature),
        }
    )


def make_trusted_key(
    private_key: ec.EllipticCurvePrivateKey,
    key_id: str,
    environment: KeyEnvironment = KeyEnvironment.PRODUCTION,
    valid_until: datetime | None = None,
) -> TrustedKey:
    return TrustedKey(
        key_id=key_id,
        environment=environment,
        algorithm=SignatureAlgorithm.ECDSA_P256_SHA256,
        public_key=private_key.public_key(),
        valid_from=KEY_VALID_FROM,
        valid_until=valid_until,
    )
