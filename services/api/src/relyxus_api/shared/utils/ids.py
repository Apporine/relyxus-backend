"""UUIDv7 identifiers for public IDs (ADR-0003 §4; context.md §5: never sequential integers).

UUIDv7 (RFC 9562 §5.7) starts with a millisecond timestamp, so new rows land at the end
of B-tree indexes and IDs sort roughly by creation time. Python 3.13 has no built-in.
"""

import secrets
import time
import uuid

_VERSION_7 = 0x7
_RFC_9562_VARIANT = 0b10
_TIMESTAMP_SHIFT = 80
_VERSION_SHIFT = 76
_RANDOM_A_SHIFT = 64
_VARIANT_SHIFT = 62
_RANDOM_A_BITS = 12
_RANDOM_B_BITS = 62


def new_uuid7() -> uuid.UUID:
    timestamp_ms = time.time_ns() // 1_000_000
    value = (
        (timestamp_ms << _TIMESTAMP_SHIFT)
        | (_VERSION_7 << _VERSION_SHIFT)
        | (secrets.randbits(_RANDOM_A_BITS) << _RANDOM_A_SHIFT)
        | (_RFC_9562_VARIANT << _VARIANT_SHIFT)
        | secrets.randbits(_RANDOM_B_BITS)
    )
    return uuid.UUID(int=value)
