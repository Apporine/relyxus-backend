import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from apporine_licensing.canonical_json import canonicalize
from apporine_licensing.envelope import parse_envelope
from apporine_licensing.errors import KeySetConfigurationError
from apporine_licensing.key_set import KeyEnvironment
from apporine_licensing.key_set_document import load_key_set_document
from apporine_licensing.signature import authenticate_envelope
from signing_support import public_key_pem

GOLDEN_VECTOR = json.loads(
    (Path(__file__).parent / "vectors" / "golden-license-v1.json").read_text(encoding="utf-8")
)


@pytest.fixture
def key_set_document(production_private_key: ec.EllipticCurvePrivateKey) -> dict[str, Any]:
    return {
        "key_set_version": 1,
        "keys": [
            {
                "key_id": "apporine-license-prod-2026-10",
                "environment": "production",
                "algorithm": "ECDSA_P256_SHA256",
                "valid_from": "2026-10-01T00:00:00Z",
                "public_key_pem": public_key_pem(production_private_key),
            }
        ],
    }


def test_document_loads_into_trusted_key_set(key_set_document: dict[str, Any]) -> None:
    key_set = load_key_set_document(json.dumps(key_set_document, indent=2).encode())

    key = key_set.find("apporine-license-prod-2026-10")
    assert key is not None
    assert key.environment is KeyEnvironment.PRODUCTION
    assert key.valid_from == datetime(2026, 10, 1, tzinfo=UTC)
    assert key.valid_until is None


def test_golden_licence_verifies_with_a_key_set_document() -> None:
    document = {
        "key_set_version": 1,
        "keys": [
            {
                "key_id": GOLDEN_VECTOR["key_id"],
                "environment": GOLDEN_VECTOR["environment"],
                "algorithm": "ECDSA_P256_SHA256",
                "valid_from": GOLDEN_VECTOR["key_valid_from"],
                "public_key_pem": GOLDEN_VECTOR["public_key_pem"],
            }
        ],
    }
    key_set = load_key_set_document(canonicalize(document))

    authenticated = authenticate_envelope(
        parse_envelope(GOLDEN_VECTOR["envelope"].encode()), key_set, KeyEnvironment.PRODUCTION
    )

    assert authenticated.signing_key.key_id == GOLDEN_VECTOR["key_id"]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"key_set_version": 2}, "unknown version"),
        ({"keys": []}, "no keys"),
        ({"comment": "x"}, "unknown member"),
    ],
)
def test_invalid_documents_are_configuration_errors(
    key_set_document: dict[str, Any], change: dict[str, object], reason: str
) -> None:
    key_set_document.update(change)

    with pytest.raises(KeySetConfigurationError):
        load_key_set_document(canonicalize(key_set_document))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", "qa"),
        ("algorithm", "RSA_PSS"),
        ("valid_from", "2026-10-01"),
        ("valid_until", "2026-09-01T00:00:00Z"),
        ("public_key_pem", "not a key"),
        ("key_id", "Bad Key"),
    ],
)
def test_invalid_key_entries_are_configuration_errors(
    key_set_document: dict[str, Any], field: str, value: str
) -> None:
    key_set_document["keys"][0][field] = value

    with pytest.raises(KeySetConfigurationError):
        load_key_set_document(canonicalize(key_set_document))


def test_private_key_in_document_is_refused(
    key_set_document: dict[str, Any], production_private_key: ec.EllipticCurvePrivateKey
) -> None:
    key_set_document["keys"][0]["public_key_pem"] = production_private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    with pytest.raises(KeySetConfigurationError, match="private key"):
        load_key_set_document(canonicalize(key_set_document))


def test_duplicate_key_ids_are_refused(key_set_document: dict[str, Any]) -> None:
    key_set_document["keys"].append(dict(key_set_document["keys"][0]))

    with pytest.raises(KeySetConfigurationError, match="Duplicate"):
        load_key_set_document(canonicalize(key_set_document))


@pytest.mark.parametrize("document", [b"", b"[]", b'{"key_set_version":1,"key_set_version":1}'])
def test_unparseable_documents_are_configuration_errors(document: bytes) -> None:
    with pytest.raises(KeySetConfigurationError):
        load_key_set_document(document)
