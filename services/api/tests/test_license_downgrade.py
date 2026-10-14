"""Licence install must reject older revisions (LIC-17.02 downgrade)."""

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from apporine_licensing.license_state import LicenseState
from apporine_licensing.payload import LicensePayload
from apporine_licensing.verifier import VerifiedLicense
from relyxus_api.modules.license.model import OrganizationLicense
from relyxus_api.modules.license.service import (
    LicenseDowngradeForbiddenError,
    LicenseRuntime,
    LicenseService,
)

LICENSE_ID = uuid.UUID("5d2a9c41-7e3b-4f80-b6a1-2c4d8e9f0a13")
CUSTOMER_ID = uuid.UUID("9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d")


def _payload(*, revision: int) -> LicensePayload:
    return LicensePayload.model_validate(
        {
            "schema_version": 1,
            "license_id": str(LICENSE_ID),
            "revision": revision,
            "customer_id": str(CUSTOMER_ID),
            "product_id": "relyxus",
            "deployment_bindings": [
                {"deployment_id": "golden-bank-prod", "allowance": "production"},
            ],
            "issued_at": "2026-10-14T08:00:00Z",
            "not_before": "2026-10-14T00:00:00Z",
            "expires_at": "2027-10-14T00:00:00Z",
            "grace_policy_id": "standard-30d",
            "entitlements": ["relyxus.advanced_replay"],
            "limits": {},
            "support_tier": "premium",
        }
    )


def _verified(revision: int) -> VerifiedLicense:
    payload = _payload(revision=revision)
    now = datetime.now(UTC)
    return VerifiedLicense(
        payload=payload,
        signing_key_id="apporine-license-golden-1",
        deployment_binding=payload.deployment_bindings[0],
        state=LicenseState.ACTIVE,
        grace_ends_at=payload.expires_at,
        evaluated_at=now,
    )


def test_install_rejects_older_revision() -> None:
    session = AsyncMock()
    organization_id = uuid.uuid4()
    current = OrganizationLicense(
        id=uuid.uuid4(),
        organization_id=organization_id,
        license_id=LICENSE_ID,
        revision=3,
        artifact="{}",
        is_current=True,
        superseded_at=None,
    )
    repository = MagicMock()
    repository.find_current = AsyncMock(return_value=current)
    service = LicenseService(repository=repository)
    runtime = LicenseRuntime(verifier=MagicMock())

    service._verify_artifact = MagicMock(return_value=_verified(revision=2))  # type: ignore[method-assign]

    with pytest.raises(LicenseDowngradeForbiddenError):
        asyncio.run(
            service.install(
                session,
                organization_id,
                "{}",
                runtime,
                datetime.now(UTC),
            )
        )
