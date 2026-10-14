"""Golden vectors and rejection cases for canonical JSON (ADR-0002 §2, LIC-19.01)."""

import pytest

from apporine_licensing.canonical_json import (
    MAX_SAFE_INTEGER,
    canonicalize,
    is_canonical,
    load_strict_json,
)
from apporine_licensing.errors import CanonicalJsonError


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"b": 2, "a": 1}, b'{"a":1,"b":2}'),
        ({"z": [3, 1, 2], "a": {"y": None, "x": True}}, b'{"a":{"x":true,"y":null},"z":[3,1,2]}'),
        ([], b"[]"),
        ({}, b"{}"),
        (False, b"false"),
        (-17, b"-17"),
        (MAX_SAFE_INTEGER, b"9007199254740991"),
        ("plain", b'"plain"'),
    ],
)
def test_canonicalize_matches_golden_vector(value: object, expected: bytes) -> None:
    assert canonicalize(value) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('quote " and backslash \\', b'"quote \\" and backslash \\\\"'),
        ("\b\t\n\f\r", b'"\\b\\t\\n\\f\\r"'),
        ("\x00\x0f\x1f", b'"\\u0000\\u000f\\u001f"'),
        ("\x7f\x80", b'"\x7f\xc2\x80"'),
        ("é€😀", '"é€😀"'.encode()),
        (chr(0x2028), ('"' + chr(0x2028) + '"').encode()),
        ("/", b'"/"'),
    ],
)
def test_strings_are_escaped_exactly_as_rfc8785(text: str, expected: bytes) -> None:
    assert canonicalize(text) == expected


def test_keys_are_ordered_by_utf16_code_units_as_in_rfc8785_example() -> None:
    value = {
        "€": "Euro Sign",
        "\r": "Carriage Return",
        "דּ": "Hebrew Letter Dalet With Dagesh",
        "1": "One",
        "\U0001f600": "Emoji: Grinning Face",
        "\u0080": "Control",
        "ö": "Latin Small Letter O With Diaeresis",
    }

    expected = (
        '{"\\r":"Carriage Return","1":"One","\u0080":"Control",'
        '"ö":"Latin Small Letter O With Diaeresis","€":"Euro Sign",'
        '"\U0001f600":"Emoji: Grinning Face","דּ":"Hebrew Letter Dalet With Dagesh"}'
    ).encode()

    assert canonicalize(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        1.0,
        float("nan"),
        MAX_SAFE_INTEGER + 1,
        -(MAX_SAFE_INTEGER + 1),
        {1: "non-string key"},
        {"a": {1, 2}},
        ("tuple",),
        "\ud800",
    ],
)
def test_canonicalize_rejects_values_outside_the_subset(value: object) -> None:
    with pytest.raises(CanonicalJsonError):
        canonicalize(value)


@pytest.mark.parametrize(
    "document",
    [
        b'{"a":1,"a":2}',
        b'{"a":1.0}',
        b'{"a":1e2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":"\xff"}',
        b'\xef\xbb\xbf{"a":1}',
        b'{"a":1',
        b"",
    ],
)
def test_load_strict_json_rejects_ambiguous_documents(document: bytes) -> None:
    with pytest.raises(CanonicalJsonError):
        load_strict_json(document)


def test_load_strict_json_parses_valid_document() -> None:
    assert load_strict_json(b'{"a":[1,"x",null,true]}') == {"a": [1, "x", None, True]}


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        (b'{"a":1,"b":2}', True),
        (b'{"b":2,"a":1}', False),
        (b'{"a": 1}', False),
        (b'{"a":"\\u00e9"}', False),
        (b'{"a":"\\u000F"}', False),
        (b'{"a":1.5}', False),
        (b'{"a":1}\n', False),
    ],
)
def test_is_canonical_accepts_only_the_exact_canonical_bytes(
    document: bytes, *, expected: bool
) -> None:
    assert is_canonical(document) is expected


def test_round_trip_is_stable() -> None:
    document = canonicalize({"nested": {"list": [{"b": 1, "a": "é"}]}, "n": 0})

    assert canonicalize(load_strict_json(document)) == document
