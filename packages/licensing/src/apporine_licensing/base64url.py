"""Strict unpadded base64url (RFC 4648 §5) with a single valid encoding per byte string."""

import base64
import binascii
import re

from apporine_licensing.errors import LicenseMalformedError

_ALPHABET = re.compile(r"[A-Za-z0-9_-]+")
_BLOCK = 4


def encode_base64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_base64url(text: str) -> bytes:
    """Decode, rejecting padding, foreign characters and non-zero trailing bits."""
    if not _ALPHABET.fullmatch(text):
        raise LicenseMalformedError("Value is not unpadded base64url")
    padding = "=" * (-len(text) % _BLOCK)
    try:
        decoded = base64.urlsafe_b64decode(text + padding)
    except (binascii.Error, ValueError) as error:
        raise LicenseMalformedError("Value is not valid base64url") from error
    if encode_base64url(decoded) != text:
        raise LicenseMalformedError("Value is not in canonical base64url form")
    return decoded
