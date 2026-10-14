from pathlib import Path

from apporine_licensing.key_set import KeyEnvironment
from relyxus_api.modules.license.key_set_loader import load_trusted_key_set_file

GOLDEN_KEY_SET = (
    Path(__file__).resolve().parents[3]
    / "packages/licensing/tests/vectors/golden-trusted-key-set-v1.json"
)


def test_loads_golden_trusted_key_set_document() -> None:
    key_set = load_trusted_key_set_file(GOLDEN_KEY_SET)
    key = key_set.find("apporine-license-golden-1")
    assert key is not None
    assert key.environment is KeyEnvironment.PRODUCTION
