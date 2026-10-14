import uuid
from datetime import UTC, datetime


def format_weak_etag(entity_id: uuid.UUID, version_timestamp: datetime) -> str:
    """Weak ETag from entity id and `updated_at` (ADR-0003 §5)."""
    version = version_timestamp.astimezone(UTC).isoformat()
    return f'W/"{entity_id}:{version}"'
