from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from apporine_licensing.errors import KeySetConfigurationError
from apporine_licensing.key_set import KeyEnvironment, TrustedKeySet, load_trusted_key
from signing_support import KEY_VALID_FROM, make_trusted_key


def _public_pem(private_key: ec.EllipticCurvePrivateKey | rsa.RSAPrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def test_loads_p256_public_key(production_private_key: ec.EllipticCurvePrivateKey) -> None:
    key = load_trusted_key(
        key_id="k1",
        environment=KeyEnvironment.PRODUCTION,
        public_key_pem=_public_pem(production_private_key),
        valid_from=KEY_VALID_FROM,
    )

    assert key.environment is KeyEnvironment.PRODUCTION


def test_private_key_material_is_refused(
    production_private_key: ec.EllipticCurvePrivateKey,
) -> None:
    private_pem = production_private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    with pytest.raises(KeySetConfigurationError, match="private key"):
        load_trusted_key(
            key_id="k1",
            environment=KeyEnvironment.PRODUCTION,
            public_key_pem=private_pem,
            valid_from=KEY_VALID_FROM,
        )


@pytest.mark.parametrize(
    "private_key",
    [
        ec.generate_private_key(ec.SECP384R1()),
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
    ],
)
def test_keys_not_matching_the_algorithm_are_refused(
    private_key: ec.EllipticCurvePrivateKey | rsa.RSAPrivateKey,
) -> None:
    with pytest.raises(KeySetConfigurationError):
        load_trusted_key(
            key_id="k1",
            environment=KeyEnvironment.PRODUCTION,
            public_key_pem=_public_pem(private_key),
            valid_from=KEY_VALID_FROM,
        )


def test_garbage_pem_is_refused() -> None:
    with pytest.raises(KeySetConfigurationError):
        load_trusted_key(
            key_id="k1",
            environment=KeyEnvironment.PRODUCTION,
            public_key_pem=b"-----BEGIN PUBLIC KEY-----\nnot a key\n-----END PUBLIC KEY-----\n",
            valid_from=KEY_VALID_FROM,
        )


def test_validity_window_must_be_ordered_and_aware(
    production_private_key: ec.EllipticCurvePrivateKey,
) -> None:
    with pytest.raises(KeySetConfigurationError):
        make_trusted_key(production_private_key, "k1", valid_until=KEY_VALID_FROM)
    with pytest.raises(KeySetConfigurationError):
        make_trusted_key(production_private_key, "k1", valid_until=datetime(2030, 1, 1))  # noqa: DTZ001


def test_signing_window_bounds_are_inclusive(
    production_private_key: ec.EllipticCurvePrivateKey,
) -> None:
    until = datetime(2027, 1, 1, tzinfo=UTC)
    key = make_trusted_key(production_private_key, "k1", valid_until=until)

    assert key.can_have_issued_at(KEY_VALID_FROM)
    assert key.can_have_issued_at(until)
    assert not key.can_have_issued_at(datetime(2025, 12, 31, tzinfo=UTC))
    assert not key.can_have_issued_at(datetime(2027, 1, 1, 0, 0, 1, tzinfo=UTC))


def test_key_set_rejects_duplicates_and_emptiness(
    production_private_key: ec.EllipticCurvePrivateKey,
) -> None:
    key = make_trusted_key(production_private_key, "k1")

    with pytest.raises(KeySetConfigurationError):
        TrustedKeySet([key, key])
    with pytest.raises(KeySetConfigurationError):
        TrustedKeySet([])
    assert TrustedKeySet([key]).find("k1") is key
    assert TrustedKeySet([key]).find("missing") is None
