"""`relyxus license inspect|verify` (DEP-23.02, LIC-15.03).

`install`, `status` and `replace` need the local licence store and are not implemented yet;
they are deliberately absent rather than stubbed (DEP-7.03).
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from apporine_licensing.base64url import decode_base64url
from apporine_licensing.envelope import parse_envelope
from apporine_licensing.key_set import KeyEnvironment
from apporine_licensing.key_set_document import load_key_set_document
from apporine_licensing.payload import UTC_TIMESTAMP_FORMAT, LicensePayload, parse_payload
from apporine_licensing.verifier import InstallationIdentity, LicenseVerifier, VerifiedLicense

type JsonObject = dict[str, object]


@dataclass(frozen=True, slots=True)
class VerifyRequest:
    license_file: Path
    key_set_file: Path
    product_id: str
    customer_id: str
    deployment_id: str
    environment: KeyEnvironment
    evaluated_at: datetime


def inspect_license(license_file: Path) -> JsonObject:
    """Decode a licence for reading. The signature is NOT checked; output says so."""
    envelope = parse_envelope(license_file.read_bytes())
    payload = parse_payload(decode_base64url(envelope.payload))
    return {
        "signature_verified": False,
        "envelope": {
            "envelope_version": envelope.envelope_version,
            "algorithm": envelope.algorithm,
            "key_id": envelope.key_id,
        },
        "payload": _describe_payload(payload),
    }


def verify_license(request: VerifyRequest) -> JsonObject:
    key_set = load_key_set_document(request.key_set_file.read_bytes())
    installation = InstallationIdentity(
        product_id=request.product_id,
        customer_id=request.customer_id,
        deployment_id=request.deployment_id,
        environment=request.environment,
    )
    verified = LicenseVerifier(key_set, installation).verify(
        request.license_file.read_bytes(), request.evaluated_at
    )
    return _describe_verification(verified)


def _describe_payload(payload: LicensePayload) -> JsonObject:
    described: JsonObject = payload.model_dump(mode="json")
    return described


def _describe_verification(verified: VerifiedLicense) -> JsonObject:
    payload = verified.payload
    return {
        "signature_verified": True,
        "state": verified.state.value,
        "license_id": payload.license_id,
        "revision": payload.revision,
        "signing_key_id": verified.signing_key_id,
        "deployment_id": verified.deployment_binding.deployment_id,
        "deployment_allowance": verified.deployment_binding.allowance.value,
        "support_tier": payload.support_tier.value,
        "not_before": _format_utc(payload.not_before),
        "expires_at": _format_utc(payload.expires_at),
        "grace_ends_at": _format_utc(verified.grace_ends_at),
        "evaluated_at": _format_utc(verified.evaluated_at),
        "entitlements": list(payload.entitlements),
        "limits": dict(payload.limits),
    }


def _format_utc(moment: datetime) -> str:
    return moment.strftime(UTC_TIMESTAMP_FORMAT)
