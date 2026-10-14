import json
from datetime import datetime
from pathlib import Path

from apporine_licensing.key_set import KeyEnvironment, TrustedKeySet, load_trusted_key


def load_key_set_from_golden_vector(path: Path) -> TrustedKeySet:
    document = json.loads(path.read_text(encoding="utf-8"))
    key = load_trusted_key(
        key_id=document["key_id"],
        environment=KeyEnvironment(document["environment"]),
        public_key_pem=document["public_key_pem"].encode(),
        valid_from=datetime.fromisoformat(document["key_valid_from"]),
    )
    return TrustedKeySet([key])
