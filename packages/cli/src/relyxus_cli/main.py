"""Entry point for the `relyxus` CLI.

Results go to stdout as JSON. Failures go to stderr as JSON with a stable error code, a
plain-language message and a safe next action, and exit non-zero (DEP-7.02).
"""

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from apporine_licensing.errors import (
    CustomerMismatchError,
    DeploymentNotLicensedError,
    KeySetConfigurationError,
    LicenseError,
    LicenseNotYetValidError,
    ProductMismatchError,
    SignatureInvalidError,
    UnknownSigningKeyError,
)
from apporine_licensing.key_set import KeyEnvironment
from relyxus_cli.license_commands import VerifyRequest, inspect_license, verify_license

EXIT_OK = 0
EXIT_LICENSE_REJECTED = 1
EXIT_CONFIGURATION_ERROR = 3
EXIT_FILE_UNREADABLE = 4

DEFAULT_PRODUCT_ID = "relyxus"
FILE_UNREADABLE_CODE = "FILE_UNREADABLE"

_DO_NOT_INSTALL = "Do not install this file."
_NEXT_ACTIONS: dict[str, str] = {
    SignatureInvalidError.code: f"{_DO_NOT_INSTALL} Request a fresh copy from Apporine "
    "through the approved delivery channel.",
    UnknownSigningKeyError.code: "Use the trusted key set shipped with this Relyxus release; "
    "if it is current, request a re-issued licence from Apporine.",
    LicenseNotYetValidError.code: "Check that the system clock is correct, or wait until "
    "the licence start date.",
    CustomerMismatchError.code: "Check --customer-id; if it is correct, the licence was "
    "issued for another customer. Contact Apporine.",
    DeploymentNotLicensedError.code: "Check --deployment-id; if it is correct, request a "
    "licence rebind for this deployment from Apporine.",
    ProductMismatchError.code: "Check --product-id; this licence is for another product.",
    KeySetConfigurationError.code: "Use the unmodified trusted key-set file shipped with "
    "this Relyxus release.",
    FILE_UNREADABLE_CODE: "Check the file path and read permissions.",
}
_DEFAULT_NEXT_ACTION = f"{_DO_NOT_INSTALL} Contact Apporine support and quote the error code."


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    try:
        if arguments.license_command == "inspect":
            result = inspect_license(arguments.file)
        else:
            result = verify_license(
                VerifyRequest(
                    license_file=arguments.file,
                    key_set_file=arguments.key_set,
                    product_id=arguments.product_id,
                    customer_id=arguments.customer_id,
                    deployment_id=arguments.deployment_id,
                    environment=arguments.environment,
                    evaluated_at=arguments.at or datetime.now(UTC),
                )
            )
    except KeySetConfigurationError as error:
        return _report_failure(error.code, str(error), EXIT_CONFIGURATION_ERROR)
    except LicenseError as error:
        return _report_failure(error.code, str(error), EXIT_LICENSE_REJECTED)
    except OSError as error:
        return _report_failure(FILE_UNREADABLE_CODE, error.strerror or "", EXIT_FILE_UNREADABLE)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return EXIT_OK


def _report_failure(code: str, message: str, exit_code: int) -> int:
    failure = {
        "error": {
            "code": code,
            "message": message,
            "next_action": _NEXT_ACTIONS.get(code, _DEFAULT_NEXT_ACTION),
        }
    }
    sys.stderr.write(json.dumps(failure, indent=2) + "\n")
    return exit_code


def _parse_utc(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise argparse.ArgumentTypeError("must include a timezone, e.g. 2027-01-15T12:00:00Z")
    return moment.astimezone(UTC)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relyxus", description="Relyxus operations CLI")
    commands = parser.add_subparsers(dest="command", required=True)
    license_parser = commands.add_parser("license", help="Commercial licence operations")
    license_commands = license_parser.add_subparsers(dest="license_command", required=True)

    inspect_parser = license_commands.add_parser(
        "inspect", help="Show a licence's contents WITHOUT verifying its signature"
    )
    inspect_parser.add_argument("--file", type=Path, required=True)

    verify_parser = license_commands.add_parser(
        "verify", help="Verify a licence offline against the trusted key set"
    )
    verify_parser.add_argument("--file", type=Path, required=True)
    verify_parser.add_argument("--key-set", type=Path, required=True)
    verify_parser.add_argument("--customer-id", required=True)
    verify_parser.add_argument("--deployment-id", required=True)
    verify_parser.add_argument("--product-id", default=DEFAULT_PRODUCT_ID)
    verify_parser.add_argument(
        "--environment",
        type=KeyEnvironment,
        choices=list(KeyEnvironment),
        default=KeyEnvironment.PRODUCTION,
    )
    verify_parser.add_argument(
        "--at", type=_parse_utc, help="Evaluate at this UTC time instead of now"
    )
    return parser


if __name__ == "__main__":
    sys.exit(main())
