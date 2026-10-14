"""Canonical JSON for licence payloads: RFC 8785 (JCS), restricted subset (ADR-0002 §2).

Only objects with string keys, arrays, strings, booleans, null and integers within the
IEEE-754 safe range are accepted. Floats are rejected rather than approximated so that a
licence has exactly one byte representation.
"""

import json

from apporine_licensing.errors import CanonicalJsonError

MAX_SAFE_INTEGER = 2**53 - 1

_SHORT_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\t": "\\t",
    "\n": "\\n",
    "\f": "\\f",
    "\r": "\\r",
}
_FIRST_NON_CONTROL_CODE_POINT = 0x20


def canonicalize(value: object) -> bytes:
    """Serialise `value` to its canonical UTF-8 bytes."""
    try:
        return _serialize(value).encode("utf-8")
    except UnicodeEncodeError as error:
        raise CanonicalJsonError("String contains an unpaired surrogate") from error


def load_strict_json(document: bytes) -> object:
    """Parse JSON, rejecting invalid UTF-8, duplicate keys, floats and NaN/Infinity."""
    try:
        text = document.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CanonicalJsonError("Document is not valid UTF-8") from error
    try:
        return json.loads(
            text,
            object_pairs_hook=_build_object_rejecting_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise CanonicalJsonError(f"Document is not valid JSON: {error.msg}") from error


def is_canonical(document: bytes) -> bool:
    """Return True when `document` parses strictly and is byte-identical to its canonical form."""
    try:
        return canonicalize(load_strict_json(document)) == document
    except CanonicalJsonError:
        return False


def _serialize(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return _serialize_integer(value)
    if isinstance(value, str):
        return _serialize_string(value)
    if isinstance(value, list):
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if isinstance(value, dict):
        return _serialize_object(value)
    raise CanonicalJsonError(f"Unsupported type for canonical JSON: {type(value).__name__}")


def _serialize_integer(value: int) -> str:
    if abs(value) > MAX_SAFE_INTEGER:
        raise CanonicalJsonError("Integer is outside the IEEE-754 safe range")
    return str(value)


def _serialize_string(value: str) -> str:
    escaped = []
    for character in value:
        if character in _SHORT_ESCAPES:
            escaped.append(_SHORT_ESCAPES[character])
        elif ord(character) < _FIRST_NON_CONTROL_CODE_POINT:
            escaped.append(f"\\u{ord(character):04x}")
        else:
            escaped.append(character)
    return '"' + "".join(escaped) + '"'


def _serialize_object(value: dict[object, object]) -> str:
    keys = list(value)
    for key in keys:
        if not isinstance(key, str):
            raise CanonicalJsonError("Object keys must be strings")
    # RFC 8785 §3.2.3: order by UTF-16 code units; big-endian bytes compare identically.
    ordered_keys = sorted(keys, key=lambda key: str(key).encode("utf-16-be", "surrogatepass"))
    members = (f"{_serialize_string(str(key))}:{_serialize(value[key])}" for key in ordered_keys)
    return "{" + ",".join(members) + "}"


def _build_object_rejecting_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    built: dict[str, object] = {}
    for key, item in pairs:
        if key in built:
            raise CanonicalJsonError(f"Duplicate object key: {key!r}")
        built[key] = item
    return built


def _reject_float(literal: str) -> object:
    raise CanonicalJsonError(f"Non-integer numbers are not allowed: {literal}")


def _reject_constant(literal: str) -> object:
    raise CanonicalJsonError(f"Non-finite numbers are not allowed: {literal}")
