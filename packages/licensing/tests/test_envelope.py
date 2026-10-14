import json
from typing import Any

import pytest

from apporine_licensing.canonical_json import canonicalize
from apporine_licensing.envelope import parse_envelope
from apporine_licensing.errors import LicenseMalformedError, UnsupportedEnvelopeVersionError


@pytest.fixture
def envelope_document() -> dict[str, Any]:
    return {
        "envelope_version": 1,
        "algorithm": "ECDSA_P256_SHA256",
        "key_id": "apporine-license-prod-2026-10",
        "payload": "eyJhIjoxfQ",
        "signature": "MEUCIQ-signature_bytes",
    }


def test_valid_envelope_parses(envelope_document: dict[str, Any]) -> None:
    envelope = parse_envelope(canonicalize(envelope_document))

    assert envelope.key_id == "apporine-license-prod-2026-10"


def test_envelope_need_not_be_canonical(envelope_document: dict[str, Any]) -> None:
    pretty = json.dumps(envelope_document, indent=2).encode()

    assert parse_envelope(pretty) == parse_envelope(canonicalize(envelope_document))


@pytest.mark.parametrize("version", [2, 99])
def test_unsupported_envelope_version_is_rejected(
    envelope_document: dict[str, Any], version: int
) -> None:
    envelope_document["envelope_version"] = version

    with pytest.raises(UnsupportedEnvelopeVersionError):
        parse_envelope(canonicalize(envelope_document))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("envelope_version", "1"),
        ("envelope_version", 0),
        ("algorithm", "ecdsa"),
        ("key_id", "Key With Spaces"),
        ("payload", "eyJhIjoxfQ=="),
        ("payload", ""),
        ("signature", "abc+/"),
    ],
)
def test_invalid_member_values_are_malformed(
    envelope_document: dict[str, Any], field: str, value: object
) -> None:
    envelope_document[field] = value

    with pytest.raises(LicenseMalformedError):
        parse_envelope(canonicalize(envelope_document))


def test_unknown_members_are_rejected(envelope_document: dict[str, Any]) -> None:
    envelope_document["comment"] = "added after signing"

    with pytest.raises(LicenseMalformedError):
        parse_envelope(canonicalize(envelope_document))


def test_missing_signature_is_malformed(envelope_document: dict[str, Any]) -> None:
    del envelope_document["signature"]

    with pytest.raises(LicenseMalformedError):
        parse_envelope(canonicalize(envelope_document))


@pytest.mark.parametrize("document", [b"", b"[]", b'"text"', b'{"key_id":"a","key_id":"b"}'])
def test_non_object_or_ambiguous_documents_are_malformed(document: bytes) -> None:
    with pytest.raises(LicenseMalformedError):
        parse_envelope(document)
