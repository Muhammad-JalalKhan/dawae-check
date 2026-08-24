"""Scan audit trail endpoint — returns scan history for a facility."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.scanned_log import ScannedLog
from app.schemas import ScanLogResponse

router = APIRouter(prefix="/scans", tags=["scans"])


@router.get("/{facility_id}", response_model=list[ScanLogResponse])
async def get_facility_scans(
    facility_id: str,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """Return scan audit trail for a given facility (most recent first)."""
    stmt = (
        select(ScannedLog)
        .where(ScannedLog.facility_id == facility_id)
        .order_by(ScannedLog.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    logs = result.scalars().all()

    return [
        ScanLogResponse(
            scan_id=str(log.scan_id),
            request_id=log.request_id,
            device_id=log.device_id,
            facility_id=log.facility_id,
            extracted_gtin=log.extracted_gtin,
            extracted_batch_number=log.extracted_batch_number,
            layer1_status=log.layer1_status,
            layer2_status=log.layer2_status,
            authenticity_score=float(log.authenticity_score),
            verdict=log.verdict,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]
