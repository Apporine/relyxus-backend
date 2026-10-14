"""Declarative base and the columns every table carries (context.md §9, MPS-20.01).

Tenancy columns (`organization_id`, `workspace_id`) are added by the tenancy mixins in the
tenancy module, not here, because organisation-level tables differ (ADR-0003 §6).
"""

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from relyxus_api.shared.utils.ids import new_uuid7

# Deterministic constraint names keep Alembic autogenerate and reviews stable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        datetime: DateTime(timezone=True),
        uuid.UUID: Uuid(as_uuid=True),
    }


class RecordColumns:
    """`id`, `created_at`, `updated_at`: required on every table (context.md §9)."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
