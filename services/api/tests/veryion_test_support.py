"""A fake Veryion licence API for tests that run the real SDK with only its HTTP replaced.

The server signs vy1 licence and vya1 activation tokens with a fixed Ed25519 test key, so the SDK
verifies them exactly as it verifies tokens from api.veryion.com.
"""

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from veryion_licensing import HttpResponse
from veryion_licensing.core.base64url import decode_base64url_strict, encode_base64url
from veryion_licensing.core.canonical import canonicalize
from veryion_licensing.core.licence_key import check_character, format_licence_key

PRODUCT = "RLX"
KID = "k-relyxus-test-1"
VERYION_URL = "https://veryion.example.test"
START = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
# A fixed seed keeps every signed token identical between runs.
SIGNING_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PUBLIC_KEY = encode_base64url(SIGNING_KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


def licence_key(random: str) -> str:
    """A key with a valid Luhn mod 32 check character, so the SDK sends it to the server."""
    return format_licence_key(PRODUCT, "STD", random + check_character(random))


GOLDEN_KEY = licence_key("ABCDEFGHJKM")
OTHER_CUSTOMER_KEY = licence_key("ZYXWVTSRQP0")
UNKNOWN_KEY = licence_key("0123456789A")
# The golden key with its check character changed: the SDK refuses it before any request.
TYPO_KEY = GOLDEN_KEY[:-1] + ("1" if GOLDEN_KEY.endswith("0") else "0")


def iso(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sign(kind: str, payload: dict[str, Any]) -> str:
    body = canonicalize(payload).encode("utf-8")
    return f"{kind}.{encode_base64url(body)}.{encode_base64url(SIGNING_KEY.sign(body))}"


def token_payload(token: str) -> dict[str, Any]:
    body = decode_base64url_strict(token.split(".")[1])
    assert body is not None
    return dict(json.loads(body))


KEY_SET = sign(
    "vyk1",
    {
        "environment": "sandbox",
        "issuedAt": iso(START - timedelta(days=30)),
        "keys": {KID: {"publicKey": PUBLIC_KEY}},
        "kid": KID,
        "organisation": "ORG-RELYXUS",
        "product": PRODUCT,
    },
)


@dataclass(frozen=True)
class SoldLicence:
    licence: str
    customer: str
    customer_name: str


def customer_uuid(public_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"https://veryion.com/customers/{public_id}")


def licence_uuid(public_id: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"https://veryion.com/licences/{public_id}")


@dataclass
class Clock:
    now: datetime = START

    def __call__(self) -> datetime:
        return self.now


@dataclass
class FakeVeryionServer:
    """The Veryion licence API as the SDK's transport sees it: activate, check in, deactivate."""

    clock: Clock
    licences: Mapping[str, SoldLicence]
    is_offline: bool = False
    calls: list[str] = field(default_factory=list)
    revisions: dict[str, int] = field(default_factory=dict)
    activations: dict[str, str] = field(default_factory=dict)
    freed: set[str] = field(default_factory=set)

    def __call__(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout: float
    ) -> HttpResponse:
        if self.is_offline:
            raise OSError("Veryion is unreachable in this test")
        path = url.removeprefix(VERYION_URL)
        self.calls.append(path)
        request = json.loads(body)
        if path == "/v1/licence/activate":
            return self._activate(request)
        if path == "/v1/licence/check-in":
            return self._check_in(request)
        if path == "/v1/licence/deactivate":
            activation = token_payload(request["activationToken"])["activation"]
            self.freed.add(activation)
            return HttpResponse(200, "{}")
        return HttpResponse(404, '{"error": {"code": "not_found"}}')

    def _activate(self, request: dict[str, Any]) -> HttpResponse:
        sold = self.licences.get(request["licenceKey"])
        if sold is None:
            return HttpResponse(
                404, '{"error": {"code": "licence_not_found", "message": "No such licence."}}'
            )
        activation = f"ACT-{len(self.activations) + 1:04d}"
        self.activations[activation] = sold.licence
        self.revisions.setdefault(sold.licence, 1)
        return self._answer(sold, activation, request["components"])

    def _check_in(self, request: dict[str, Any]) -> HttpResponse:
        previous = token_payload(request["activationToken"])
        sold = next(s for s in self.licences.values() if s.licence == previous["licence"])
        self.revisions[sold.licence] += 1
        return self._answer(sold, previous["activation"], request["components"])

    def _answer(
        self, sold: SoldLicence, activation: str, components: dict[str, str]
    ) -> HttpResponse:
        now = self.clock.now
        revision = self.revisions[sold.licence]
        licence = sign(
            "vy1",
            {
                "checkInHours": 24,
                "customer": {"id": sold.customer, "name": sold.customer_name},
                "edition": {"code": "STD", "name": "Standard"},
                "entitlements": {"feature.export": False, "feature.replay": True, "seats": 25},
                "environment": "sandbox",
                "expires": "2027-11-25T00:00:00Z",
                "graceUntil": "2027-12-09T00:00:00Z",
                "issuedAt": iso(now),
                "kid": KID,
                "licence": sold.licence,
                "model": "subscription",
                "organisation": "ORG-RELYXUS",
                "product": PRODUCT,
                "requiresActivation": True,
                "revision": revision,
                "starts": "2026-11-01T00:00:00Z",
            },
        )
        token = sign(
            "vya1",
            {
                "activation": activation,
                "components": components,
                "environment": "sandbox",
                "issuedAt": iso(now),
                "kid": KID,
                "leaseUntil": iso(now + timedelta(days=14)),
                "licence": sold.licence,
                "product": PRODUCT,
                "revision": revision,
                "slot": 1,
                "state": "active",
            },
        )
        return HttpResponse(200, json.dumps({"licence": licence, "activation": {"token": token}}))


GOLDEN = SoldLicence("LIC-GDQ89A", "CUS-NYA95A", "Bravo Pay")
OTHER = SoldLicence("LIC-OTH3R1", "CUS-OTH3R1", "Someone Else")
