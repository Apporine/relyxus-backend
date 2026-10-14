import json
import logging

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from api_test_support import make_settings
from relyxus_api.app import create_app
from relyxus_api.shared.errors.app_errors import (
    AppError,
    AuthenticationRequiredError,
    ConflictError,
    DependencyUnavailableError,
    LicenseProblemError,
    NotFoundError,
    PermissionDeniedError,
    PolicyDeniedError,
    ValidationFailedError,
)
from relyxus_api.shared.observability.correlation import CORRELATION_HEADER
from relyxus_api.shared.observability.logging import JsonLogFormatter

PROBLEM_JSON = "application/problem+json"


class IncidentNotFoundError(NotFoundError):
    code = "INCIDENT_NOT_FOUND"


class DeclareRequest(BaseModel):
    title: str
    severity: int


ERRORS: list[AppError] = [
    ValidationFailedError("bad"),
    AuthenticationRequiredError("no token"),
    PermissionDeniedError("no access"),
    PolicyDeniedError("blocked by policy"),
    LicenseProblemError("licence expired"),
    IncidentNotFoundError("No incident with this ID is visible to you."),
    ConflictError("stale ETag"),
    DependencyUnavailableError("database unreachable"),
]


def _build_test_app() -> FastAPI:
    app = create_app(make_settings())
    router = APIRouter()

    @router.get("/raise/{index}")
    def raise_error(index: int) -> None:
        raise ERRORS[index]

    @router.post("/declare")
    def declare(request: DeclareRequest) -> DeclareRequest:
        return request

    @router.get("/crash")
    def crash() -> None:
        raise RuntimeError("SELECT secret FROM internal_table")

    app.include_router(router)
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_test_app(), raise_server_exceptions=False)


@pytest.mark.parametrize("index", range(len(ERRORS)))
def test_each_error_category_becomes_problem_details(client: TestClient, index: int) -> None:
    error = ERRORS[index]

    response = client.get(f"/raise/{index}")

    body = response.json()
    assert response.status_code == error.status_code
    assert response.headers["content-type"] == PROBLEM_JSON
    assert body["code"] == error.code
    assert body["status"] == error.status_code
    assert body["detail"] == error.detail
    assert body["type"] == "urn:relyxus:problem:" + error.code.lower().replace("_", "-")
    assert body["instance"] == f"/raise/{index}"
    assert body["correlation_id"] == response.headers[CORRELATION_HEADER]


def test_feature_errors_keep_their_own_code(client: TestClient) -> None:
    body = client.get("/raise/5").json()

    assert body["code"] == "INCIDENT_NOT_FOUND"
    assert body["type"] == "urn:relyxus:problem:incident-not-found"


def test_validation_errors_list_fields_without_echoing_input(client: TestClient) -> None:
    response = client.post("/declare", json={"severity": "SEV1-<script>"})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "VALIDATION_FAILED"
    assert {problem["field"] for problem in body["errors"]} == {"body.title", "body.severity"}
    assert "<script>" not in response.text


def test_unknown_route_and_method_are_problem_details(client: TestClient) -> None:
    assert client.get("/nowhere").json()["code"] == "ROUTE_NOT_FOUND"
    assert client.delete("/health").json()["code"] == "METHOD_NOT_ALLOWED"


def test_unexpected_error_leaks_nothing(client: TestClient) -> None:
    response = client.get("/crash")

    body = response.json()
    assert response.status_code == 500
    assert body["code"] == "INTERNAL_ERROR"
    assert "SELECT" not in response.text
    assert "Traceback" not in response.text
    assert body["correlation_id"] == response.headers[CORRELATION_HEADER]


def test_caller_correlation_id_is_echoed(client: TestClient) -> None:
    response = client.get("/health", headers={CORRELATION_HEADER: "trace-abc-12345"})

    assert response.headers[CORRELATION_HEADER] == "trace-abc-12345"


@pytest.mark.parametrize("unsafe", ["short", "has spaces in it", "x" * 200, "inject\nfake-log"])
def test_unsafe_correlation_id_is_replaced(client: TestClient, unsafe: str) -> None:
    response = client.get("/health", headers={CORRELATION_HEADER: unsafe.replace("\n", "%0A")})

    assert response.headers[CORRELATION_HEADER] != unsafe
    assert len(response.headers[CORRELATION_HEADER]) == 36


def test_request_log_line_is_json_with_correlation_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        client.get(
            "/health?token=should-not-be-logged", headers={CORRELATION_HEADER: "trace-log-0001"}
        )

    record = next(r for r in caplog.records if r.getMessage() == "request completed")
    line = json.loads(JsonLogFormatter().format(record))
    assert line["correlation_id"] == "trace-log-0001"
    assert line["http_path"] == "/health"
    assert line["http_status"] == 200
    assert "should-not-be-logged" not in json.dumps(line)
