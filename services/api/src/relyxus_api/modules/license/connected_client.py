"""Outbound fetch for signed commercial status snapshots (LIC-10.02, LIC-10.03)."""

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from relyxus_api.shared.errors.app_errors import DependencyUnavailableError


class LicenseStatusFetchError(DependencyUnavailableError):
    """The licensing status endpoint could not be reached or returned an error response."""


def fetch_status_snapshot_document(url: str, timeout_seconds: float) -> bytes:
    request = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
    except (HTTPError, URLError, TimeoutError) as error:
        raise LicenseStatusFetchError(
            "Could not retrieve a signed licence status snapshot."
        ) from error
    if not body:
        raise LicenseStatusFetchError("Licence status snapshot response was empty.")
    return body
