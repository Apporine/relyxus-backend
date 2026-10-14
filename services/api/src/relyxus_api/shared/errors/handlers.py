"""The one global error handler (context.md §8). Controllers never build error responses.

Every failure becomes RFC 9457 problem details. Clients never see stack traces, SQL,
internal paths or input values; the full context goes to the log with the correlation ID.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from relyxus_api.shared.errors.app_errors import AppError
from relyxus_api.shared.errors.problem_details import (
    PROBLEM_JSON_MEDIA_TYPE,
    FieldProblem,
    ProblemDetails,
    build_problem_type,
)
from relyxus_api.shared.observability.correlation import CORRELATION_HEADER, get_correlation_id

logger = logging.getLogger(__name__)

_HTTP_ERROR_CODES = {
    status.HTTP_404_NOT_FOUND: ("ROUTE_NOT_FOUND", "Not found"),
    status.HTTP_405_METHOD_NOT_ALLOWED: ("METHOD_NOT_ALLOWED", "Method not allowed"),
}
_INTERNAL_DETAIL = "An unexpected error occurred. Quote the correlation ID when contacting support."


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unexpected_error)


def _build_problem(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    errors: list[FieldProblem] | None = None,
) -> ProblemDetails:
    return ProblemDetails(
        type=build_problem_type(code),
        title=title,
        status=status_code,
        detail=detail,
        instance=request.url.path,
        code=code,
        correlation_id=get_correlation_id(),
        errors=errors,
    )


def _problem_response(
    problem: ProblemDetails, extra_headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        problem.model_dump(exclude_none=True),
        status_code=problem.status,
        media_type=PROBLEM_JSON_MEDIA_TYPE,
        headers={CORRELATION_HEADER: problem.correlation_id, **(extra_headers or {})},
    )


async def _handle_app_error(request: Request, error: AppError) -> JSONResponse:
    log_level = (
        logging.ERROR
        if error.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
        else logging.INFO
    )
    logger.log(log_level, "request failed", extra={"error_code": error.code})
    problem = _build_problem(
        request,
        status_code=error.status_code,
        code=error.code,
        title=error.title,
        detail=error.detail,
    )
    return _problem_response(problem, error.response_headers)


async def _handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    field_problems = [
        FieldProblem(field=".".join(str(part) for part in detail["loc"]), message=detail["msg"])
        for detail in error.errors()
    ]
    return _problem_response(
        _build_problem(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_FAILED",
            title="Validation failed",
            detail="The request is invalid; see errors for each field.",
            errors=field_problems,
        )
    )


async def _handle_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
    code, title = _HTTP_ERROR_CODES.get(error.status_code, (f"HTTP_{error.status_code}", "Error"))
    return _problem_response(
        _build_problem(
            request,
            status_code=error.status_code,
            code=code,
            title=title,
            detail=error.detail if isinstance(error.detail, str) else title,
        )
    )


async def _handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    logger.exception("unhandled error", exc_info=error)
    return _problem_response(
        _build_problem(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            title="Internal error",
            detail=_INTERNAL_DETAIL,
        )
    )
