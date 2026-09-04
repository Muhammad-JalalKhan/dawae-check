"""BatchRegistry model – maps to the `batch_registry` table."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

_UUID = Uuid().with_variant(UUID(as_uuid=True), "postgresql")


class BatchRegistry(Base):
    __tablename__ = "batch_registry"
    __table_args__ = (
        # Natural key — powers ON CONFLICT (batch_number) DO UPDATE upserts.
        UniqueConstraint("batch_number", name="uq_batch_registry_batch_number"),
        Index("idx_batch_registry_gtin", "gtin"),
        Index("idx_batch_registry_drap", "drap_reg_number"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        _UUID,
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False)
    gtin: Mapped[str | None] = mapped_column(String(14), nullable=True)
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    drap_reg_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mfg_lic_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mfg_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    official_expiry: Mapped[date] = mapped_column(Date, nullable=False)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )

    # Relationships
    scanned_logs: Mapped[list["ScannedLog"]] = relationship(  # noqa: F821
        "ScannedLog", back_populates="matched_batch"
    )

    def __repr__(self) -> str:
        return f"<BatchRegistry {self.brand_name} batch={self.batch_number}>"
