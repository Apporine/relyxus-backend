"""Entry hashing for the audit chain (ADR-0003 §6).

hash = SHA-256 over the RFC 8785 canonical JSON of every hashed field, including the
previous entry's hash, so changing, removing or reordering any entry breaks every later
link. Audit state must therefore stay within canonical JSON: strings, integers, booleans,
null, lists and objects (no floats; record decimals as strings).
"""

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from apporine_licensing.canonical_json import canonicalize

HASH_ALGORITHM_VERSION = 1
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def occurred_at_for_hash(moment: datetime) -> str:
    """Normalize to UTC before hashing; naive values from PostgreSQL are treated as UTC."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime(_TIMESTAMP_FORMAT)


def _optional_text(value: uuid.UUID | None) -> str | None:
    return None if value is None else str(value)


def compute_entry_hash(
    *,
    previous_hash: str | None,
    chain_id: uuid.UUID,
    sequence: int,
    fields: dict[str, Any],
    occurred_at: datetime,
) -> str:
    document = {
        "v": HASH_ALGORITHM_VERSION,
        "previous_hash": previous_hash,
        "chain_id": str(chain_id),
        "sequence": sequence,
        "occurred_at": occurred_at_for_hash(occurred_at),
        **{
            key: str(value) if isinstance(value, uuid.UUID) else value
            for key, value in fields.items()
        },
    }
    return hashlib.sha256(canonicalize(document)).hexdigest()


def hashed_fields(  # noqa: PLR0913
    *,
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID | None,
    actor_type: str,
    actor_user_id: uuid.UUID | None,
    effective_user_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: str | None,
    outcome: str,
    before_state: dict[str, Any] | None,
    after_state: dict[str, Any] | None,
    correlation_id: str,
) -> dict[str, Any]:
    """The event fields covered by the hash, in one place for writing and verifying."""
    return {
        "organization_id": str(organization_id),
        "workspace_id": _optional_text(workspace_id),
        "actor_type": actor_type,
        "actor_user_id": _optional_text(actor_user_id),
        "effective_user_id": _optional_text(effective_user_id),
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "outcome": outcome,
        "before_state": before_state,
        "after_state": after_state,
        "correlation_id": correlation_id,
    }
