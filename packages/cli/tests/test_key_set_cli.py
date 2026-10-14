import json
from pathlib import Path

from _pytest.capture import CaptureFixture

from relyxus_cli.main import main

GOLDEN_KEY_SET = (
    Path(__file__).resolve().parents[3]
    / "packages/licensing/tests/vectors/golden-trusted-key-set-v1.json"
)


def test_validate_key_set_prints_summary(capsys: CaptureFixture[str]) -> None:
    exit_code = main(["key-set", "validate", "--file", str(GOLDEN_KEY_SET)])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["key_count"] == 1
    assert "apporine-license-golden-1" in payload["key_ids"]
