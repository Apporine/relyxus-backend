from datetime import UTC, datetime
from typing import Any

import pytest

from apporine_licensing.canonical_json import canonicalize
from apporine_licensing.errors import (
    LicenseMalformedError,
    LicensePayloadInvalidError,
    NonCanonicalPayloadError,
    UnsupportedSchemaVersionError,
)
from apporine_licensing.payload import DeploymentAllowance, SupportTier, parse_payload


def test_valid_payload_parses_into_typed_model(payload_document: dict[str, Any]) -> None:
    payload = parse_payload(canonicalize(payload_document))

    assert payload.product_id == "relyxus"
    assert payload.expires_at == datetime(2027, 10, 1, tzinfo=UTC)
    assert payload.deployment_bindings[1].allowance is DeploymentAllowance.DISASTER_RECOVERY
    assert payload.support_tier is SupportTier.ENTERPRISE


def test_model_reproduces_the_exact_signed_bytes(payload_document: dict[str, Any]) -> None:
    payload_bytes = canonicalize(payload_document)

    assert parse_payload(payload_bytes).to_canonical_bytes() == payload_bytes


def test_non_canonical_bytes_are_rejected(payload_document: dict[str, Any]) -> None:
    pretty = canonicalize(payload_document).replace(b'"revision":1', b'"revision": 1')

    with pytest.raises(NonCanonicalPayloadError):
        parse_payload(pretty)


@pytest.mark.parametrize("document", [b"not json", b'{"a":1.5}', b'{"a":1,"a":1}'])
def test_unparseable_payload_is_malformed(document: bytes) -> None:
    with pytest.raises(LicenseMalformedError):
        parse_payload(document)


def test_payload_must_be_an_object() -> None:
    with pytest.raises(LicenseMalformedError):
        parse_payload(b"[1]")


@pytest.mark.parametrize("version", [0, 2, "1", True, None])
def test_unknown_schema_version_is_rejected(
    payload_document: dict[str, Any], version: object
) -> None:
    payload_document["schema_version"] = version

    with pytest.raises(UnsupportedSchemaVersionError):
        parse_payload(canonicalize(payload_document))


INVALID_FIELD_VALUES = [
    ("license_id", "0B7E2F64-81C9-4D3A-A5F2-9E4C6D8B1A37"),
    ("revision", 0),
    ("revision", "1"),
    ("customer_id", "acme"),
    ("product_id", "Relyxus"),
    ("deployment_bindings", []),
    ("deployment_bindings", [{"deployment_id": "pod-7f9c", "allowance": "everything"}]),
    ("issued_at", "2026-10-01T09:00:00+00:00"),
    ("issued_at", "2026-10-01 09:00:00Z"),
    ("expires_at", "2027-10-01T00:00:00.000Z"),
    ("not_before", "2026-13-01T00:00:00Z"),
    ("grace_policy_id", ""),
    ("entitlements", ["premium_connectors"]),
    ("limits", {"relyxus.production_deployments": -1}),
    ("support_tier", "platinum"),
]


@pytest.mark.parametrize(("field", "value"), INVALID_FIELD_VALUES)
def test_field_rules_are_enforced(
    payload_document: dict[str, Any], field: str, value: object
) -> None:
    payload_document[field] = value

    with pytest.raises(LicensePayloadInvalidError):
        parse_payload(canonicalize(payload_document))


@pytest.mark.parametrize("field", ["license_id", "expires_at", "support_tier"])
def test_required_fields_cannot_be_omitted(payload_document: dict[str, Any], field: str) -> None:
    del payload_document[field]

    with pytest.raises(LicensePayloadInvalidError):
        parse_payload(canonicalize(payload_document))


@pytest.mark.parametrize("field", ["database_password", "api_key", "customer_name"])
def test_unknown_fields_are_rejected_so_no_secret_can_be_added(
    payload_document: dict[str, Any], field: str
) -> None:
    payload_document[field] = "value"

    with pytest.raises(LicensePayloadInvalidError):
        parse_payload(canonicalize(payload_document))


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"expires_at": "2026-09-30T00:00:00Z"}, "issued after expiry"),
        ({"not_before": "2027-10-01T00:00:00Z"}, "starts at expiry"),
        (
            {
                "deployment_bindings": [
                    {"deployment_id": "acme-bank-prod-eu", "allowance": "production"},
                    {"deployment_id": "acme-bank-prod-eu", "allowance": "disaster_recovery"},
                ]
            },
            "duplicate deployment",
        ),
        ({"entitlements": ["relyxus.b", "relyxus.a"]}, "unsorted entitlements"),
        ({"entitlements": ["relyxus.a", "relyxus.a"]}, "duplicate entitlements"),
        ({"entitlements": ["otherproduct.feature"]}, "foreign entitlement namespace"),
        ({"limits": {"otherproduct.seats": 5}}, "foreign limit namespace"),
    ],
)
def test_cross_field_rules_are_enforced(
    payload_document: dict[str, Any], changes: dict[str, object], reason: str
) -> None:
    payload_document.update(changes)

    with pytest.raises(LicensePayloadInvalidError):
        parse_payload(canonicalize(payload_document))


def test_error_message_does_not_echo_payload_values(payload_document: dict[str, Any]) -> None:
    payload_document["customer_id"] = "secret-looking-customer-reference"

    with pytest.raises(LicensePayloadInvalidError) as raised:
        parse_payload(canonicalize(payload_document))

    assert "secret-looking-customer-reference" not in str(raised.value)
    assert "customer_id" in str(raised.value)
