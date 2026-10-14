from relyxus_api.shared.errors.app_errors import PreconditionFailedError


def assert_if_match(actual_etag: str, if_match: str | None) -> None:
    """Validate `If-Match` for optimistic concurrency (412 on mismatch)."""
    if if_match is None:
        return
    candidate = if_match.strip()
    if candidate == "*":
        return
    if candidate != actual_etag:
        raise PreconditionFailedError(
            "The resource has changed since you last read it; refresh and retry."
        )
