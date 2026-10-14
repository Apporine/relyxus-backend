from pathlib import Path

from apporine_licensing.errors import KeySetConfigurationError
from apporine_licensing.key_set import TrustedKeySet
from apporine_licensing.key_set_document import load_key_set_document


def load_trusted_key_set_file(path: Path) -> TrustedKeySet:
    try:
        document = path.read_bytes()
    except OSError as error:
        raise KeySetConfigurationError(f"Cannot read trusted key set at {path}") from error
    return load_key_set_document(document)
