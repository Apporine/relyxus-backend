"""Signature authentication: golden vector, tampering, wrong keys, rotation (LIC-19.01/19.02)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from apporine_licensing.base64url import decode_base64url, encode_base64url
from apporine_licensing.canonical_json import canonicalize, load_strict_json
from apporine_licensing.envelope import parse_envelope
from apporine_licensing.errors import (
    LicenseMalformedError,
    SignatureInvalidError,
    SigningKeyEnvironmentError,
    UnknownSigningKeyError,
    UnsupportedAlgorithmError,
)
from apporine_licensing.key_set import KeyEnvironment, TrustedKey, TrustedKeySet, load_trusted_key
from apporine_licensing.signature import authenticate_envelope
from signing_support import PRODUCTION_KEY_ID, make_trusted_key, sign_envelope

GOLDEN_VECTOR = json.loads(
    (Path(__file__).parent / "vectors" / "golden-license-v1.json").read_text(encoding="utf-8")
)
PRODUCTION = KeyEnvironment.PRODUCTION


def _golden_key_set() -> TrustedKeySet:
    return TrustedKeySet(
        [
            load_trusted_key(
                key_id=GOLDEN_VECTOR["key_id"],
                environment=KeyEnvironment(GOLDEN_VECTOR["environment"]),
                public_key_pem=GOLDEN_VECTOR["public_key_pem"].encode(),
                valid_from=datetime.fromisoformat(GOLDEN_VECTOR["key_valid_from"]),
            )
        ]
    )


def _with_envelope_member(envelope_bytes: bytes, member: str, value: object) -> bytes:
    document = load_strict_json(envelope_bytes)
    assert isinstance(document, dict)
    document[member] = value
    return canonicalize(document)


def test_golden_vector_authenticates_to_the_recorded_payload() -> None:
    envelope = parse_envelope(GOLDEN_VECTOR["envelope"].encode())

    authenticated = authenticate_envelope(envelope, _golden_key_set(), PRODUCTION)

    assert authenticated.payload_bytes == canonicalize(GOLDEN_VECTOR["payload"])


def test_golden_vector_with_one_flipped_payload_byte_is_rejected() -> None:
    envelope_bytes = GOLDEN_VECTOR["envelope"].encode()
    payload = bytearray(decode_base64url(parse_envelope(envelope_bytes).payload))
    payload[payload.index(b'"revision":3') + len('"revision":')] = ord("4")
    tampered = _with_envelope_member(envelope_bytes, "payload", encode_base64url(bytes(payload)))

    with pytest.raises(SignatureInvalidError):
        authenticate_envelope(parse_envelope(tampered), _golden_key_set(), PRODUCTION)


def test_valid_signature_returns_payload_and_key(
    production_private_key: ec.EllipticCurvePrivateKey,
    production_key: TrustedKey,
    payload_document: dict[str, Any],
) -> None:
    payload_bytes = canonicalize(payload_document)
    envelope_bytes = sign_envelope(payload_bytes, production_private_key, PRODUCTION_KEY_ID)

    authenticated = authenticate_envelope(
        parse_envelope(envelope_bytes), TrustedKeySet([production_key]), PRODUCTION
    )

    assert authenticated.payload_bytes == payload_bytes
    assert authenticated.signing_key is production_key


def test_payload_swapped_for_another_licence_is_rejected(
    production_private_key: ec.EllipticCurvePrivateKey,
    production_key: TrustedKey,
    payload_document: dict[str, Any],
) -> None:
    envelope_bytes = sign_envelope(canonicalize(payload_document), production_private_key, "k")
    payload_document["expires_at"] = "2099-01-01T00:00:00Z"
    forged = _with_envelope_member(
        envelope_bytes, "payload", encode_base64url(canonicalize(payload_document))
    )
    forged = _with_envelope_member(forged, "key_id", PRODUCTION_KEY_ID)

    with pytest.raises(SignatureInvalidError):
        authenticate_envelope(parse_envelope(forged), TrustedKeySet([production_key]), PRODUCTION)


@pytest.mark.parametrize(
    "signature", ["AAAA", encode_base64url(b"\x30\x06\x02\x01\x01\x02\x01\x01")]
)
def test_garbage_signature_is_rejected(
    production_private_key: ec.EllipticCurvePrivateKey,
    production_key: TrustedKey,
    payload_document: dict[str, Any],
    signature: str,
) -> None:
    envelope_bytes = sign_envelope(
        canonicalize(payload_document), production_private_key, PRODUCTION_KEY_ID
    )
    corrupted = _with_envelope_member(envelope_bytes, "signature", signature)

    with pytest.raises(SignatureInvalidError):
        authenticate_envelope(
            parse_envelope(corrupted), TrustedKeySet([production_key]), PRODUCTION
        )


def test_licence_forged_with_an_attacker_key_under_a_trusted_key_id_is_rejected(
    other_private_key: ec.EllipticCurvePrivateKey,
    production_key: TrustedKey,
    payload_document: dict[str, Any],
) -> None:
    forged = sign_envelope(canonicalize(payload_document), other_private_key, PRODUCTION_KEY_ID)

    with pytest.raises(SignatureInvalidError):
        authenticate_envelope(parse_envelope(forged), TrustedKeySet([production_key]), PRODUCTION)


def test_unknown_key_id_is_rejected(
    production_private_key: ec.EllipticCurvePrivateKey,
    production_key: TrustedKey,
    payload_document: dict[str, Any],
) -> None:
    envelope_bytes = sign_envelope(canonicalize(payload_document), production_private_key, "k9")

    with pytest.raises(UnknownSigningKeyError):
        authenticate_envelope(
            parse_envelope(envelope_bytes), TrustedKeySet([production_key]), PRODUCTION
        )


def test_non_production_key_never_verifies_a_production_installation(
    other_private_key: ec.EllipticCurvePrivateKey,
    payload_document: dict[str, Any],
) -> None:
    staging_key = make_trusted_key(other_private_key, "staging-1", KeyEnvironment.STAGING)
    envelope_bytes = sign_envelope(canonicalize(payload_document), other_private_key, "staging-1")

    with pytest.raises(SigningKeyEnvironmentError):
        authenticate_envelope(
            parse_envelope(envelope_bytes), TrustedKeySet([staging_key]), PRODUCTION
        )


def test_unsupported_algorithm_is_rejected(
    production_private_key: ec.EllipticCurvePrivateKey,
    production_key: TrustedKey,
    payload_document: dict[str, Any],
) -> None:
    envelope_bytes = sign_envelope(
        canonicalize(payload_document), production_private_key, PRODUCTION_KEY_ID
    )
    downgraded = _with_envelope_member(envelope_bytes, "algorithm", "NONE")

    with pytest.raises(UnsupportedAlgorithmError):
        authenticate_envelope(
            parse_envelope(downgraded), TrustedKeySet([production_key]), PRODUCTION
        )


def test_padded_payload_encoding_is_rejected(
    production_private_key: ec.EllipticCurvePrivateKey,
    production_key: TrustedKey,
    payload_document: dict[str, Any],
) -> None:
    envelope_bytes = sign_envelope(b'{"a":1}', production_private_key, PRODUCTION_KEY_ID)
    padded = _with_envelope_member(envelope_bytes, "payload", "eyJhIjoxfR")

    with pytest.raises(LicenseMalformedError):
        authenticate_envelope(parse_envelope(padded), TrustedKeySet([production_key]), PRODUCTION)


def test_both_keys_verify_during_rotation_overlap(
    production_private_key: ec.EllipticCurvePrivateKey,
    other_private_key: ec.EllipticCurvePrivateKey,
    payload_document: dict[str, Any],
) -> None:
    retiring = make_trusted_key(
        production_private_key, "prod-1", valid_until=datetime(2026, 12, 31, tzinfo=UTC)
    )
    current = make_trusted_key(other_private_key, "prod-2")
    key_set = TrustedKeySet([retiring, current])
    payload_bytes = canonicalize(payload_document)

    for private_key, key_id in [(production_private_key, "prod-1"), (other_private_key, "prod-2")]:
        envelope = parse_envelope(sign_envelope(payload_bytes, private_key, key_id))

        assert authenticate_envelope(envelope, key_set, PRODUCTION).signing_key.key_id == key_id
