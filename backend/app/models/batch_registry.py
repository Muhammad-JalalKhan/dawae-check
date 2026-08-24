"""BatchRegistry model – maps to the `batch_registry` table."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

_UUID = Uuid().with_variant(UUID(as_uuid=True), "postgresql")


class BatchRegistry(Base):
    __tablename__ = "batch_registry"
    __table_args__ = (
        UniqueConstraint("gtin", "batch_number", name="uq_gtin_batch"),
        Index("idx_batch_registry_gtin_batch", "gtin", "batch_number"),
        Index("idx_batch_registry_drap", "drap_reg_number"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        _UUID,
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.text("gen_random_uuid()"),
    )
    manufacturer_id: Mapped[uuid.UUID] = mapped_column(
        _UUID,
        ForeignKey("manufacturers.manufacturer_id"),
        nullable=False,
    )
    gtin: Mapped[str] = mapped_column(String(20), nullable=False)
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False)
    drap_reg_number: Mapped[str] = mapped_column(String(100), nullable=False)
    official_expiry: Mapped[date] = mapped_column(Date, nullable=False)
    manufacture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )

    # Relationships
    manufacturer: Mapped["Manufacturer"] = relationship(  # noqa: F821
        "Manufacturer", back_populates="batches"
    )
    scanned_logs: Mapped[list["ScannedLog"]] = relationship(  # noqa: F821
        "ScannedLog", back_populates="matched_batch"
    )

    def __repr__(self) -> str:
        return f"<BatchRegistry {self.brand_name} batch={self.batch_number}>"
