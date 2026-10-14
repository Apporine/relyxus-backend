"""RFC 9457 problem details body (ADR-0003 §1)."""

from pydantic import BaseModel, ConfigDict, Field

PROBLEM_JSON_MEDIA_TYPE = "application/problem+json"
PROBLEM_TYPE_PREFIX = "urn:relyxus:problem:"


class FieldProblem(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str = Field(examples=["body.title"])
    message: str = Field(examples=["Field required"])


class ProblemDetails(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str = Field(examples=["urn:relyxus:problem:not-found"])
    title: str = Field(examples=["Not found"])
    status: int = Field(examples=[404])
    detail: str = Field(examples=["No incident with this ID is visible to you."])
    instance: str = Field(examples=["/api/v1/incidents/0192f0c4-7d1e-7a3b-9c2d-5e6f7a8b9c0d"])
    code: str = Field(examples=["NOT_FOUND"])
    correlation_id: str = Field(examples=["5f0c2b1e-6a4d-4c8e-9b7a-1d2e3f4a5b6c"])
    errors: list[FieldProblem] | None = Field(default=None, examples=[None])


def build_problem_type(code: str) -> str:
    return PROBLEM_TYPE_PREFIX + code.lower().replace("_", "-")


def _problem_responses(*status_codes: int) -> dict[int | str, dict[str, object]]:
    """OpenAPI `responses` entries documenting problem-details bodies for these statuses."""
    return {
        status_code: {"model": ProblemDetails, "content": {PROBLEM_JSON_MEDIA_TYPE: {}}}
        for status_code in status_codes
    }


PROBLEM_RESPONSES = _problem_responses(422, 500)
AUTHENTICATED_RESPONSES = _problem_responses(401, 403)
