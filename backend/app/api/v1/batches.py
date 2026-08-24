"""Batch-related API endpoints (register + lookup)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.batch_registry import BatchRegistry
from app.schemas import BatchCreate, BatchResponse

router = APIRouter(prefix="/batches", tags=["batches"])


def _batch_to_response(batch: BatchRegistry) -> BatchResponse:
    """Convert a BatchRegistry ORM object to a BatchResponse schema."""
    return BatchResponse(
        batch_id=str(batch.batch_id),
        manufacturer_id=str(batch.manufacturer_id),
        gtin=batch.gtin,
        brand_name=batch.brand_name,
        batch_number=batch.batch_number,
        drap_reg_number=batch.drap_reg_number,
        official_expiry=batch.official_expiry,
        manufacture_date=batch.manufacture_date,
        is_active=batch.is_active,
    )


@router.post("", response_model=BatchResponse, status_code=201)
async def create_batch(
    payload: BatchCreate,
    session: AsyncSession = Depends(get_session),
):
    """Admin: register a new batch in the registry."""
    # Check for duplicate (gtin, batch_number)
    stmt = select(BatchRegistry).where(
        BatchRegistry.gtin == payload.gtin,
        BatchRegistry.batch_number == payload.batch_number,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Batch already exists: gtin={payload.gtin}, batch_number={payload.batch_number}",
        )

    batch = BatchRegistry(
        manufacturer_id=uuid.UUID(payload.manufacturer_id),
        gtin=payload.gtin,
        brand_name=payload.brand_name,
        batch_number=payload.batch_number,
        drap_reg_number=payload.drap_reg_number,
        official_expiry=payload.official_expiry,
        manufacture_date=payload.manufacture_date,
    )
    session.add(batch)
    await session.commit()
    await session.refresh(batch)

    return _batch_to_response(batch)


@router.get("/{gtin}/{batch_number}", response_model=BatchResponse)
async def lookup_batch(
    gtin: str,
    batch_number: str,
    session: AsyncSession = Depends(get_session),
):
    """Lookup a batch record by GTIN and batch number."""
    stmt = select(BatchRegistry).where(
        BatchRegistry.gtin == gtin,
        BatchRegistry.batch_number == batch_number,
    )
    result = await session.execute(stmt)
    batch = result.scalar_one_or_none()

    if batch is None:
        raise HTTPException(
            status_code=404,
            detail=f"Batch not found: gtin={gtin}, batch_number={batch_number}",
        )

    return _batch_to_response(batch)
