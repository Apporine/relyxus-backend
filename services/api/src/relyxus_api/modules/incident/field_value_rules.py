"""Rules for custom field values (MPS-8A.04, MPS-20.28).

`normalise_value` checks a value against its field's data type and returns the stored
form: canonical JSON without floats (numbers as decimal strings, money as minor units plus
an ISO 4217 code, ADR-0003), date-times in UTC. `is_applicable` applies the display
condition (incident type and severity). `missing_required` lists the applicable active
fields required at or before a lifecycle stage that have no value.
"""

import re
import uuid
from collections.abc import Collection
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from relyxus_api.modules.access.repository import AccessRepository
from relyxus_api.modules.access.service import WorkspaceAccessService
from relyxus_api.modules.catalog.repository import CatalogRepository
from relyxus_api.modules.incident.field_model import (
    REQUIRABLE_STAGES,
    CustomFieldDefinition,
    FieldDataType,
)
from relyxus_api.modules.incident.lifecycle import IncidentLifecycleState
from relyxus_api.modules.incident.model import Incident
from relyxus_api.modules.team.repository import TeamRepository
from relyxus_api.shared.errors.app_errors import ValidationFailedError

TEXT_MAX_LENGTH = 5000
URL_MAX_LENGTH = 2000
_CURRENCY = re.compile(r"^[A-Z]{3}$")


class FieldValueInvalidError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_FIELD_VALUE_INVALID"


class FieldNotApplicableError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_FIELD_NOT_APPLICABLE"


class RequiredFieldsMissingError(ValidationFailedError):
    code: ClassVar[str] = "INCIDENT_REQUIRED_FIELDS_MISSING"


def is_applicable(field: CustomFieldDefinition, incident: Incident) -> bool:
    condition = field.display_condition
    type_ids = condition.get("incident_type_ids") or []
    severities = condition.get("severities") or []
    if type_ids and str(incident.incident_type_id) not in type_ids:
        return False
    return not severities or incident.severity in severities


def missing_required(
    fields: Collection[CustomFieldDefinition],
    incident: Incident,
    filled_field_ids: Collection[uuid.UUID],
    target: IncidentLifecycleState,
) -> list[str]:
    """Keys of applicable fields required at or before `target` that have no value."""
    if target not in REQUIRABLE_STAGES:
        return []
    reached = REQUIRABLE_STAGES.index(target)
    return [
        field.key
        for field in fields
        if field.archived_at is None
        and field.required_at_stage is not None
        and REQUIRABLE_STAGES.index(IncidentLifecycleState(field.required_at_stage)) <= reached
        and field.id not in filled_field_ids
        and is_applicable(field, incident)
    ]


def require_complete(
    fields: Collection[CustomFieldDefinition],
    incident: Incident,
    filled_field_ids: Collection[uuid.UUID],
    target: IncidentLifecycleState,
) -> None:
    missing = missing_required(fields, incident, filled_field_ids, target)
    if missing:
        raise RequiredFieldsMissingError(
            f"Fill these fields before the incident is {target.value}: {', '.join(missing)}."
        )


class FieldValueValidator:
    """Checks values that reference other records (users, teams, services)."""

    def __init__(
        self,
        access: WorkspaceAccessService | None = None,
        teams: TeamRepository | None = None,
        catalog: CatalogRepository | None = None,
    ) -> None:
        self._access = access or WorkspaceAccessService(AccessRepository())
        self._teams = teams or TeamRepository()
        self._catalog = catalog or CatalogRepository()

    async def normalise(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        field: CustomFieldDefinition,
        raw: Any,
    ) -> Any:
        data_type = FieldDataType(field.data_type)
        if data_type in {FieldDataType.USER, FieldDataType.TEAM, FieldDataType.SERVICE}:
            record_id = _uuid(raw, field.key)
            exists = await self._reference_exists(session, workspace_id, data_type, record_id)
            if not exists:
                raise FieldValueInvalidError(
                    f"'{field.key}' must name a {data_type.value} of this workspace."
                )
            return str(record_id)
        return normalise_plain(field, raw)

    async def _reference_exists(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        data_type: FieldDataType,
        record_id: uuid.UUID,
    ) -> bool:
        if data_type is FieldDataType.USER:
            return await self._access.is_workspace_member(session, record_id, workspace_id)
        if data_type is FieldDataType.TEAM:
            return await self._teams.find_in_workspace(session, workspace_id, record_id) is not None
        service = await self._catalog.find_in_workspace(session, workspace_id, record_id)
        return service is not None and service.archived_at is None


def normalise_plain(field: CustomFieldDefinition, raw: Any) -> Any:  # noqa: PLR0911
    """Types that need no lookups. One branch per data type."""
    data_type = FieldDataType(field.data_type)
    key = field.key
    if data_type is FieldDataType.TEXT:
        if not isinstance(raw, str) or not raw.strip() or len(raw) > TEXT_MAX_LENGTH:
            raise FieldValueInvalidError(f"'{key}' needs text up to {TEXT_MAX_LENGTH} characters.")
        return raw.strip()
    if data_type is FieldDataType.NUMBER:
        return _decimal_string(raw, key)
    if data_type is FieldDataType.CURRENCY:
        return _money(raw, key)
    if data_type is FieldDataType.DATE_TIME:
        return _date_time(raw, key)
    if data_type is FieldDataType.YES_NO:
        if not isinstance(raw, bool):
            raise FieldValueInvalidError(f"'{key}' needs true or false.")
        return raw
    if data_type is FieldDataType.URL:
        return _url(raw, key)
    allowed = [option["value"] for option in field.options]
    if data_type is FieldDataType.SINGLE_CHOICE:
        if raw not in allowed:
            raise FieldValueInvalidError(f"'{key}' must be one of: {', '.join(allowed)}.")
        return raw
    if (
        not isinstance(raw, list)
        or not raw
        or len(set(map(str, raw))) != len(raw)
        or any(choice not in allowed for choice in raw)
    ):
        raise FieldValueInvalidError(
            f"'{key}' needs one or more distinct values from: {', '.join(allowed)}."
        )
    return [choice for choice in allowed if choice in raw]


def _uuid(raw: Any, key: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw))
    except ValueError as error:
        raise FieldValueInvalidError(f"'{key}' needs an ID.") from error


def _decimal_string(raw: Any, key: str) -> str:
    if isinstance(raw, bool) or not isinstance(raw, int | float | str):
        raise FieldValueInvalidError(f"'{key}' needs a number.")
    try:
        number = Decimal(str(raw))
    except InvalidOperation as error:
        raise FieldValueInvalidError(f"'{key}' needs a number.") from error
    if not number.is_finite():
        raise FieldValueInvalidError(f"'{key}' needs a finite number.")
    return format(number.normalize(), "f")


def _money(raw: Any, key: str) -> dict[str, object]:
    if not isinstance(raw, dict) or set(raw) != {"amount_minor", "currency"}:
        raise FieldValueInvalidError(f"'{key}' needs {{amount_minor, currency}}.")
    amount, currency = raw["amount_minor"], raw["currency"]
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise FieldValueInvalidError(f"'{key}' amount_minor must be a whole number.")
    if not isinstance(currency, str) or not _CURRENCY.match(currency):
        raise FieldValueInvalidError(f"'{key}' currency must be an ISO 4217 code, e.g. EUR.")
    return {"amount_minor": amount, "currency": currency}


def _date_time(raw: Any, key: str) -> str:
    try:
        moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError as error:
        raise FieldValueInvalidError(f"'{key}' needs an ISO 8601 date-time.") from error
    if moment.tzinfo is None:
        raise FieldValueInvalidError(f"'{key}' needs a date-time with a time zone.")
    return moment.astimezone(UTC).isoformat()


def _url(raw: Any, key: str) -> str:
    parsed = urlparse(raw) if isinstance(raw, str) else None
    if (
        parsed is None
        or parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or len(raw) > URL_MAX_LENGTH
    ):
        raise FieldValueInvalidError(f"'{key}' needs an http(s) URL.")
    return str(raw)
