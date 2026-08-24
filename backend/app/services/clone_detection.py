"""Clone detection service – checks for serial cloning anomalies.

Looks at scanned_logs within the configured time window and counts
distinct facility_ids for a given (gtin, batch_number). If the count
meets or exceeds the threshold, the serial is considered cloned.

Called by db_gate.check_database_gate() after batch existence and
expiry have been confirmed (Layer 1, Step 4).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.scanned_log import ScannedLog


async def check_serial_clone(
    session: AsyncSession,
    extracted_gtin: str,
    extracted_batch_number: str,
) -> bool:
    """Check whether a serial has been scanned across too many distinct facilities.

    Parameters
    ----------
    session : AsyncSession
        Active SQLAlchemy async session.
    extracted_gtin : str
        GTIN from the scan.
    extracted_batch_number : str
        Batch number from the scan.

    Returns
    -------
    bool
        True if clone detected (distinct facility count >= threshold),
        False otherwise.
    """
    window = timedelta(hours=settings.CLONE_DETECTION_WINDOW_HOURS)
    cutoff = datetime.now(timezone.utc) - window

    stmt = (
        select(func.count(func.distinct(ScannedLog.facility_id)))
        .where(
            ScannedLog.extracted_gtin == extracted_gtin,
            ScannedLog.extracted_batch_number == extracted_batch_number,
            ScannedLog.created_at >= cutoff,
        )
    )

    result = await session.execute(stmt)
    distinct_facilities: int = result.scalar() or 0

    return distinct_facilities >= settings.CLONE_DETECTION_LOCATION_THRESHOLD
