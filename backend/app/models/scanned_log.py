"""ScannedLog model – maps to the `scanned_logs` table."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Double,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

# Dialect-aware types: JSONB on Postgres, JSON elsewhere
_JSONB = JSON().with_variant(JSONB(), "postgresql")
_UUID = Uuid().with_variant(UUID(as_uuid=True), "postgresql")


class ScannedLog(Base):
    __tablename__ = "scanned_logs"
    __table_args__ = (
        Index("idx_scanned_logs_gtin_batch", "extracted_gtin", "extracted_batch_number"),
        Index("idx_scanned_logs_device", "device_id"),
        Index("idx_scanned_logs_created_at", "created_at"),
    )

    scan_id: Mapped[uuid.UUID] = mapped_column(
        _UUID,
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.text("gen_random_uuid()"),
    )
    request_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False)
    facility_id: Mapped[str] = mapped_column(String(100), nullable=False)
    matched_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        _UUID,
        ForeignKey("batch_registry.batch_id"),
        nullable=True,
    )
    extracted_gtin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extracted_batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extracted_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    extracted_drap_reg: Mapped[str | None] = mapped_column(String(100), nullable=True)
    layer1_status: Mapped[str] = mapped_column(String(20), nullable=False)
    layer1_reasons: Mapped[dict | None] = mapped_column(_JSONB, nullable=True)
    layer2_status: Mapped[str] = mapped_column(String(20), nullable=False)
    layer2_print_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    layer2_defects: Mapped[dict | None] = mapped_column(_JSONB, nullable=True)
    authenticity_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Double, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Double, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )

    # Relationships
    matched_batch: Mapped["BatchRegistry | None"] = relationship(  # noqa: F821
        "BatchRegistry", back_populates="scanned_logs"
    )

    def __repr__(self) -> str:
        return f"<ScannedLog {self.request_id} verdict={self.verdict}>"
