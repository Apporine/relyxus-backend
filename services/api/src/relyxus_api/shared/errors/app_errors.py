"""Typed application errors (context.md §8, MP-34.01).

Services raise these; the global handler turns them into RFC 9457 problem details. Each
class covers one category MP-34.01 requires us to distinguish. Features subclass them with
their own stable `code`, e.g. `class IncidentNotFoundError(NotFoundError)`.
"""

from typing import ClassVar

from fastapi import status


class AppError(Exception):
    code: ClassVar[str] = "INTERNAL_ERROR"
    status_code: ClassVar[int] = status.HTTP_500_INTERNAL_SERVER_ERROR
    title: ClassVar[str] = "Internal error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ValidationFailedError(AppError):
    code: ClassVar[str] = "VALIDATION_FAILED"
    status_code: ClassVar[int] = status.HTTP_422_UNPROCESSABLE_CONTENT
    title: ClassVar[str] = "Validation failed"


class AuthenticationRequiredError(AppError):
    code: ClassVar[str] = "AUTHENTICATION_REQUIRED"
    status_code: ClassVar[int] = status.HTTP_401_UNAUTHORIZED
    title: ClassVar[str] = "Authentication required"


class PermissionDeniedError(AppError):
    code: ClassVar[str] = "PERMISSION_DENIED"
    status_code: ClassVar[int] = status.HTTP_403_FORBIDDEN
    title: ClassVar[str] = "Permission denied"


class PolicyDeniedError(AppError):
    """An OPA policy decision refused the operation (governance, not permissions)."""

    code: ClassVar[str] = "POLICY_DENIED"
    status_code: ClassVar[int] = status.HTTP_403_FORBIDDEN
    title: ClassVar[str] = "Denied by policy"


class LicenseProblemError(AppError):
    """A commercial licence state blocks this operation. Never used for security controls."""

    code: ClassVar[str] = "LICENSE_PROBLEM"
    status_code: ClassVar[int] = status.HTTP_403_FORBIDDEN
    title: ClassVar[str] = "Licence does not permit this operation"


class NotFoundError(AppError):
    code: ClassVar[str] = "NOT_FOUND"
    status_code: ClassVar[int] = status.HTTP_404_NOT_FOUND
    title: ClassVar[str] = "Not found"


class ConflictError(AppError):
    code: ClassVar[str] = "CONFLICT"
    status_code: ClassVar[int] = status.HTTP_409_CONFLICT
    title: ClassVar[str] = "Conflict"


class DependencyUnavailableError(AppError):
    """A required downstream system failed; never report success in this case (MP-34.01)."""

    code: ClassVar[str] = "DEPENDENCY_UNAVAILABLE"
    status_code: ClassVar[int] = status.HTTP_503_SERVICE_UNAVAILABLE
    title: ClassVar[str] = "Dependency unavailable"
