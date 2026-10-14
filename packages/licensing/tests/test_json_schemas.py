from pathlib import Path

from apporine_licensing.json_schemas import render_json_schemas

SCHEMA_DIRECTORY = Path(__file__).resolve().parents[2] / "schemas" / "licensing"


def test_committed_json_schemas_match_the_models() -> None:
    for file_name, expected in render_json_schemas().items():
        committed = (SCHEMA_DIRECTORY / file_name).read_text(encoding="utf-8")

        assert committed == expected, (
            f"{file_name} is stale; regenerate with "
            "`uv run python -m apporine_licensing.json_schemas packages/schemas/licensing`"
        )


def test_payload_schema_is_closed_against_extra_fields() -> None:
    payload_schema = render_json_schemas()["license-payload.v1.schema.json"]

    assert '"additionalProperties": false' in payload_schema
