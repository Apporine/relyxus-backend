from pathlib import Path

from apporine_licensing.key_set_document import load_key_set_document


def validate_key_set_file(path: Path) -> dict[str, object]:
    key_set = load_key_set_document(path.read_bytes())
    key_ids = key_set.key_ids()
    return {
        "valid": True,
        "key_set_version": 1,
        "key_ids": list(key_ids),
        "key_count": len(key_ids),
    }
