"""Export the licence JSON Schemas shipped in the install kit (DEP-23.01).

The Pydantic models are the single source; the committed schema files are generated from
them and a test fails on drift (context.md §6: never maintain both by hand).

Regenerate with: ``uv run python -m apporine_licensing.json_schemas packages/schemas/licensing``
"""

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from apporine_licensing.envelope import LicenseEnvelope
from apporine_licensing.key_set_document import TrustedKeySetDocument
from apporine_licensing.payload import LicensePayload

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

SCHEMA_MODELS: dict[str, tuple[str, type[BaseModel]]] = {
    "license-envelope.v1.schema.json": (
        "urn:apporine:licensing:license-envelope:v1",
        LicenseEnvelope,
    ),
    "license-payload.v1.schema.json": ("urn:apporine:licensing:license-payload:v1", LicensePayload),
    "trusted-key-set.v1.schema.json": (
        "urn:apporine:licensing:trusted-key-set:v1",
        TrustedKeySetDocument,
    ),
}


def render_json_schemas() -> dict[str, str]:
    """Return each schema file name mapped to its exact file content."""
    rendered = {}
    for file_name, (schema_id, model) in SCHEMA_MODELS.items():
        schema = {"$schema": JSON_SCHEMA_DIALECT, "$id": schema_id, **model.model_json_schema()}
        rendered[file_name] = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    return rendered


def write_json_schemas(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for file_name, content in render_json_schemas().items():
        (directory / file_name).write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    write_json_schemas(Path(sys.argv[1]))
