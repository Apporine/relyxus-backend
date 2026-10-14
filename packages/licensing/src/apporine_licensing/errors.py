"""Typed licensing errors, each with a stable machine-readable code (context.md §8, MP-34.01)."""

from typing import ClassVar


class LicenseError(Exception):
    """Base class for every licensing error."""

    code: ClassVar[str] = "LICENSE_ERROR"


class CanonicalJsonError(LicenseError):
    """A value or document is outside the canonical JSON subset defined in ADR-0002 §2."""

    code: ClassVar[str] = "LICENSE_CANONICAL_JSON_INVALID"


class LicenseVerificationError(LicenseError):
    """The artifact must not be trusted. Verification fails closed (ADR-0002 §6)."""

    code: ClassVar[str] = "LICENSE_INVALID"


class LicenseMalformedError(LicenseVerificationError):
    """The envelope is not well-formed JSON of the expected shape."""

    code: ClassVar[str] = "LICENSE_MALFORMED"


class UnsupportedEnvelopeVersionError(LicenseVerificationError):
    code: ClassVar[str] = "LICENSE_UNSUPPORTED_ENVELOPE_VERSION"


class NonCanonicalPayloadError(LicenseVerificationError):
    """The signed payload bytes are not in canonical form (ADR-0002 §1)."""

    code: ClassVar[str] = "LICENSE_PAYLOAD_NOT_CANONICAL"


class UnsupportedSchemaVersionError(LicenseVerificationError):
    code: ClassVar[str] = "LICENSE_UNSUPPORTED_SCHEMA_VERSION"


class LicensePayloadInvalidError(LicenseVerificationError):
    """The payload violates the licence payload schema."""

    code: ClassVar[str] = "LICENSE_PAYLOAD_INVALID"


class UnsupportedAlgorithmError(LicenseVerificationError):
    code: ClassVar[str] = "LICENSE_UNSUPPORTED_ALGORITHM"


class UnknownSigningKeyError(LicenseVerificationError):
    """The envelope names a key that is not in the trusted key set."""

    code: ClassVar[str] = "LICENSE_UNKNOWN_SIGNING_KEY"


class SigningKeyEnvironmentError(LicenseVerificationError):
    """The signing key belongs to another environment, e.g. staging vs production (LIC-6.03)."""

    code: ClassVar[str] = "LICENSE_SIGNING_KEY_ENVIRONMENT_MISMATCH"


class SignatureInvalidError(LicenseVerificationError):
    """The signature does not match the payload: tampered, re-signed or corrupted."""

    code: ClassVar[str] = "LICENSE_SIGNATURE_INVALID"


class KeySetConfigurationError(LicenseError):
    """The trusted key set is invalid: a deployment configuration fault, not a bad licence."""

    code: ClassVar[str] = "LICENSE_KEY_SET_INVALID"
