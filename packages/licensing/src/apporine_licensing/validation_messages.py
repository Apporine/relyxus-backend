"""Safe summaries of schema validation failures.

Messages name the failing fields and rule types but never echo input values, so licence
contents and customer identifiers do not leak into logs (DEP-23.03, MP-28.01).
"""

from pydantic import ValidationError


def summarize_validation_error(error: ValidationError) -> str:
    problems = (
        f"{'.'.join(str(part) for part in detail['loc']) or '<root>'}: {detail['type']}"
        for detail in error.errors(include_input=False, include_url=False)
    )
    return "; ".join(problems)
