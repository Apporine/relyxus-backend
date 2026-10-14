"""Export the OpenAPI contract to the shared schema area (ADR-0003, MP-9.01).

The FastAPI app is the single source; the committed file is generated from it and a test
fails on drift, so every contract change shows up as a reviewed diff in the PR.

Regenerate with: ``uv run python -m relyxus_api.openapi_export packages/schemas/openapi``
"""

import json
import sys
from pathlib import Path

from pydantic import AnyHttpUrl, SecretStr

from relyxus_api.app import create_app
from relyxus_api.shared.config.settings import Environment, Settings

OPENAPI_FILE_NAME = "relyxus-api.openapi.json"
# Servers differ per environment, so the committed contract is rendered without them.
# The engine is lazy, so this placeholder database is never contacted during export.
_EXPORT_SETTINGS = Settings(
    environment=Environment.LOCAL,
    public_base_url=AnyHttpUrl("http://localhost:8000"),
    database_url=SecretStr("postgresql+psycopg://export@localhost:1/unused"),
    oidc_issuer_url="https://id.example.invalid/realms/relyxus",
    oidc_audience="relyxus-api",
)


def render_openapi() -> str:
    contract = create_app(_EXPORT_SETTINGS).openapi()
    contract.pop("servers", None)
    return json.dumps(contract, indent=2, sort_keys=True) + "\n"


def write_openapi(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / OPENAPI_FILE_NAME).write_text(render_openapi(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    write_openapi(Path(sys.argv[1]))
