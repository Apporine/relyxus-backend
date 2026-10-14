import pytest

from apporine_licensing.base64url import decode_base64url, encode_base64url
from apporine_licensing.errors import LicenseMalformedError


@pytest.mark.parametrize(
    ("raw", "encoded"),
    [(b"", ""), (b"f", "Zg"), (b"fo", "Zm8"), (b"foo", "Zm9v"), (b"\xfb\xff", "-_8")],
)
def test_round_trip_matches_rfc4648_vectors(raw: bytes, encoded: str) -> None:
    assert encode_base64url(raw) == encoded
    if encoded:
        assert decode_base64url(encoded) == raw


@pytest.mark.parametrize("text", ["", "Zg==", "Zm9v\n", "+/8", "Zh", "Z", "Zm9v Zg"])
def test_non_canonical_or_foreign_encodings_are_rejected(text: str) -> None:
    with pytest.raises(LicenseMalformedError):
        decode_base64url(text)
