"""Typed licensing errors, each with a stable machine-readable code (context.md §8, MP-34.01)."""

from typing import ClassVar


class LicenseError(Exception):
    """Base class for every licensing error."""

    code: ClassVar[str] = "LICENSE_ERROR"


class CanonicalJsonError(LicenseError):
    """A value or document is outside the canonical JSON subset defined in ADR-0002 §2."""

    code: ClassVar[str] = "LICENSE_CANONICAL_JSON_INVALID"
