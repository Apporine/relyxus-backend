from datetime import UTC, datetime

from apporine_licensing.key_set import KeyEnvironment, TrustedKeySet, load_trusted_key


def test_key_ids_lists_sorted_key_ids() -> None:
    key = load_trusted_key(
        key_id="b-key",
        environment=KeyEnvironment.PRODUCTION,
        public_key_pem=(
            b"-----BEGIN PUBLIC KEY-----\n"
            b"MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEy7RsRP9KAm0dyYoN4sWpLmTZitnE\n"
            b"DLY4rT+xb2UyZUZz9kzMigXOc2LcSsj+YnVCmN+XwuykkDahdRe7NqxKTA==\n"
            b"-----END PUBLIC KEY-----\n"
        ),
        valid_from=datetime(2026, 1, 1, tzinfo=UTC),
    )
    other = load_trusted_key(
        key_id="a-key",
        environment=KeyEnvironment.PRODUCTION,
        public_key_pem=(
            b"-----BEGIN PUBLIC KEY-----\n"
            b"MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEy7RsRP9KAm0dyYoN4sWpLmTZitnE\n"
            b"DLY4rT+xb2UyZUZz9kzMigXOc2LcSsj+YnVCmN+XwuykkDahdRe7NqxKTA==\n"
            b"-----END PUBLIC KEY-----\n"
        ),
        valid_from=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert TrustedKeySet([key, other]).key_ids() == ("a-key", "b-key")
