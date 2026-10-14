"""Cross-cutting HTTP and API constants (context.md §2)."""

WORKSPACE_HEADER = "X-Relyxus-Workspace-Id"
CORRELATION_HEADER = "X-Correlation-Id"
IDEMPOTENCY_HEADER = "Idempotency-Key"

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100
MAX_CURSOR_LENGTH = 512

MAX_IDEMPOTENCY_KEY_LENGTH = 128
