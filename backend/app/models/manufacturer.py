"""Manufacturer model – maps to the `manufacturers` table."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Text, DateTime, Uuid, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

_UUID = Uuid().with_variant(UUID(as_uuid=True), "postgresql")


class Manufacturer(Base):
    __tablename__ = "manufacturers"

    manufacturer_id: Mapped[uuid.UUID] = mapped_column(
        _UUID,
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.text("gen_random_uuid()"),
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    drap_license_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    batches: Mapped[list["BatchRegistry"]] = relationship(  # noqa: F821
        "BatchRegistry", back_populates="manufacturer"
    )

    def __repr__(self) -> str:
        return f"<Manufacturer {self.company_name}>"
