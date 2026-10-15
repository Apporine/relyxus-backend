"""Outbound fetch for signed commercial status snapshots (LIC-10.02, LIC-10.03)."""

from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from relyxus_api.shared.errors.app_errors import DependencyUnavailableError

_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})


class LicenseStatusFetchError(DependencyUnavailableError):
    """The licensing status endpoint could not be reached or returned an error response."""


def fetch_status_snapshot_document(url: str, timeout_seconds: float) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_URL_SCHEMES or not parsed.netloc:
        raise LicenseStatusFetchError("Licence status URL must be http or https with a host.")
    request = Request(  # noqa: S310
        url,
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            body = response.read()
    except (HTTPError, URLError, TimeoutError) as error:
        raise LicenseStatusFetchError(
            "Could not retrieve a signed licence status snapshot."
        ) from error
    if not body:
        raise LicenseStatusFetchError("Licence status snapshot response was empty.")
    return body
