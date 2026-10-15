import json
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from apporine_licensing.canonical_json import canonicalize
from relyxus_cli.main import (
    EXIT_CONFIGURATION_ERROR,
    EXIT_FILE_UNREADABLE,
    EXIT_LICENSE_REJECTED,
    EXIT_OK,
    main,
)
from signing_support import CUSTOMER_ID, DEPLOYMENT_ID, LICENSE_ID, public_key_pem, sign_envelope

KEY_ID = "apporine-license-cli-test-1"
PAYLOAD: dict[str, Any] = {
    "schema_version": 1,
    "license_id": LICENSE_ID,
    "revision": 2,
    "customer_id": CUSTOMER_ID,
    "product_id": "relyxus",
    "deployment_bindings": [{"deployment_id": DEPLOYMENT_ID, "allowance": "production"}],
    "issued_at": "2026-10-01T09:00:00Z",
    "not_before": "2026-10-01T00:00:00Z",
    "expires_at": "2027-10-01T00:00:00Z",
    "grace_policy_id": "standard-30d",
    "entitlements": ["relyxus.premium_connectors"],
    "limits": {"relyxus.production_deployments": 1},
    "support_tier": "standard",
}


@pytest.fixture(scope="module")
def private_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def license_file(tmp_path: Path, private_key: ec.EllipticCurvePrivateKey) -> Path:
    path = tmp_path / "relyxus.license"
    path.write_bytes(sign_envelope(canonicalize(PAYLOAD), private_key, KEY_ID))
    return path


@pytest.fixture
def key_set_file(tmp_path: Path, private_key: ec.EllipticCurvePrivateKey) -> Path:
    path = tmp_path / "trusted-key-set.json"
    entry = {
        "key_id": KEY_ID,
        "environment": "production",
        "algorithm": "ECDSA_P256_SHA256",
        "valid_from": "2026-01-01T00:00:00Z",
        "public_key_pem": public_key_pem(private_key),
    }
    path.write_text(json.dumps({"key_set_version": 1, "keys": [entry]}), encoding="utf-8")
    return path


def _verify_arguments(license_file: Path, key_set_file: Path, *extra: str) -> list[str]:
    return [
        "license", "verify",
        "--file", str(license_file),
        "--key-set", str(key_set_file),
        "--customer-id", CUSTOMER_ID,
        "--deployment-id", DEPLOYMENT_ID,
        "--at", "2027-01-15T12:00:00Z",
        *extra,
    ]  # fmt: skip


def _error_from(captured: pytest.CaptureFixture[str]) -> dict[str, str]:
    error: dict[str, str] = json.loads(captured.readouterr().err)["error"]
    return error


def test_inspect_shows_contents_and_says_signature_is_unverified(
    license_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["license", "inspect", "--file", str(license_file)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == EXIT_OK
    assert output["signature_verified"] is False
    assert output["envelope"]["key_id"] == KEY_ID
    assert output["payload"]["license_id"] == LICENSE_ID


def test_import_emits_verified_artifact_for_install(
    license_file: Path, key_set_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "license",
            "import",
            "--file",
            str(license_file),
            "--key-set",
            str(key_set_file),
            "--customer-id",
            CUSTOMER_ID,
            "--deployment-id",
            DEPLOYMENT_ID,
            "--at",
            "2027-01-15T12:00:00Z",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == EXIT_OK
    assert output["ready_for_install"] is True
    assert output["artifact"] == license_file.read_text(encoding="utf-8")
    assert output["verification"]["state"] == "active"
    assert "license/install" in output["next_step"]


def test_verify_reports_active_licence(
    license_file: Path, key_set_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(_verify_arguments(license_file, key_set_file))

    output = json.loads(capsys.readouterr().out)
    assert exit_code == EXIT_OK
    assert output["signature_verified"] is True
    assert output["state"] == "active"
    assert output["revision"] == 2
    assert output["deployment_allowance"] == "production"
    assert output["grace_ends_at"] == "2027-10-31T00:00:00Z"


def test_verify_reports_expiry_as_state_with_success_exit(
    license_file: Path, key_set_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _verify_arguments(license_file, key_set_file)
    arguments[arguments.index("--at") + 1] = "2028-01-01T00:00:00Z"

    exit_code = main(arguments)

    assert exit_code == EXIT_OK
    assert json.loads(capsys.readouterr().out)["state"] == "expired"


def test_tampered_licence_is_rejected_with_code_and_next_action(
    license_file: Path, key_set_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    envelope = json.loads(license_file.read_bytes())
    envelope["signature"] = envelope["signature"][::-1]
    license_file.write_text(json.dumps(envelope), encoding="utf-8")

    exit_code = main(_verify_arguments(license_file, key_set_file))

    error = _error_from(capsys)
    assert exit_code == EXIT_LICENSE_REJECTED
    assert error["code"].startswith("LICENSE_")
    assert error["next_action"].startswith("Do not install this file.")


def test_wrong_deployment_explains_rebind(
    license_file: Path, key_set_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = _verify_arguments(license_file, key_set_file)
    arguments[arguments.index("--deployment-id") + 1] = "other-deployment"

    exit_code = main(arguments)

    error = _error_from(capsys)
    assert exit_code == EXIT_LICENSE_REJECTED
    assert error["code"] == "LICENSE_DEPLOYMENT_NOT_BOUND"
    assert "rebind" in error["next_action"]


def test_staging_environment_does_not_accept_production_keys(
    license_file: Path, key_set_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(_verify_arguments(license_file, key_set_file, "--environment", "staging"))

    assert exit_code == EXIT_LICENSE_REJECTED
    assert _error_from(capsys)["code"] == "LICENSE_SIGNING_KEY_ENVIRONMENT_MISMATCH"


def test_invalid_key_set_is_a_configuration_error(
    license_file: Path, key_set_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    key_set_file.write_text('{"key_set_version": 1, "keys": []}', encoding="utf-8")

    exit_code = main(_verify_arguments(license_file, key_set_file))

    assert exit_code == EXIT_CONFIGURATION_ERROR
    assert _error_from(capsys)["code"] == "LICENSE_KEY_SET_INVALID"


def test_missing_file_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["license", "inspect", "--file", str(tmp_path / "missing.license")])

    assert exit_code == EXIT_FILE_UNREADABLE
    assert _error_from(capsys)["code"] == "FILE_UNREADABLE"


@pytest.mark.parametrize(
    "arguments",
    [
        ["license"],
        ["license", "verify", "--file", "x"],
        ["license", "status"],
        ["license", "verify", "--file", "x", "--key-set", "y", "--customer-id", "c",
         "--deployment-id", "d", "--at", "2027-01-15T12:00:00"],
    ],
)  # fmt: skip
def test_usage_errors_exit_with_argparse_code(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(arguments)

    assert raised.value.code == 2


def test_console_script_is_registered() -> None:
    scripts = entry_points(group="console_scripts")

    assert scripts["relyxus"].value == "relyxus_cli.main:main"
