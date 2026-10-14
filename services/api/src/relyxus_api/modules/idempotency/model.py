import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relyxus_api.shared.db.base import Base, RecordColumns


class IdempotencyRecord(RecordColumns, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_idempotency_records_organization_id_idempotency_key",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_method: Mapped[str] = mapped_column(String(16))
    request_path: Mapped[str] = mapped_column(String(256))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict[str, object] | None] = mapped_column(JSONB)
