"""DB Gate service – Layer-1 batch lookup, expiry verification, and clone detection.

Performs a deterministic database gate check:
1. Look up (gtin, batch_number) in batch_registry.
2. If no match → FAILED (unregistered batch).
3. If match but expiry mismatch → FAILED (expiry mismatch).
4. If match and expiry matches → run clone detection.
   4a. Clone detected → FAILED (cloned serial), s_rule=50.
   4b. No clone → PASSED, s_rule=100.

This is an isolated function so the gate logic can be swapped later.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch_registry import BatchRegistry
from app.services.clone_detection import check_serial_clone


async def check_database_gate(
    session: AsyncSession,
    extracted_gtin: str,
    extracted_batch_number: str,
    extracted_expiry: str | date,
    facility_id: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """Layer-1 database gate: batch lookup + expiry verification.

    Parameters
    ----------
    session : AsyncSession
        Active SQLAlchemy async session.
    extracted_gtin : str
        GTIN extracted from the medicine image / OCR.
    extracted_batch_number : str
        Batch number extracted from the medicine image / OCR.
    extracted_expiry : str | date
        Expiry date extracted from the medicine image / OCR.
        Accepts ``YYYY-MM-DD`` string or a ``date`` object.
    facility_id : str
        Identifier of the facility performing the scan.
    latitude, longitude : float | None
        Optional GPS coordinates of the scan location (reserved for future use).

    Returns
    -------
    dict
        Keys: ``status``, ``reasons``, ``matched_batch_id``, ``s_db``,
        ``s_rule``, ``matched_record``.
    """

    # Normalise extracted_expiry to a date object for comparison
    if isinstance(extracted_expiry, str):
        extracted_expiry = date.fromisoformat(extracted_expiry)

    # ── Step 1: Look up (gtin, batch_number) in batch_registry ──────────
    stmt = select(BatchRegistry).where(
        BatchRegistry.gtin == extracted_gtin,
        BatchRegistry.batch_number == extracted_batch_number,
    )
    result = await session.execute(stmt)
    batch: BatchRegistry | None = result.scalar_one_or_none()

    # ── Step 2: No match → FAILED, unregistered batch ───────────────────
    if batch is None:
        return {
            "status": "FAILED",
            "reasons": ["Unregistered batch"],
            "matched_batch_id": None,
            "s_db": 0,
            "s_rule": 0,
            "matched_record": None,
        }

    # Build matched_record helper
    matched_record = {
        "gtin": batch.gtin,
        "brand_name": batch.brand_name,
        "batch_number": batch.batch_number,
        "official_expiry": str(batch.official_expiry),
    }

    # ── Step 3: Expiry mismatch → FAILED ────────────────────────────────
    if extracted_expiry != batch.official_expiry:
        return {
            "status": "FAILED",
            "reasons": [
                f"Expiry mismatch: extracted {extracted_expiry} vs official {batch.official_expiry}"
            ],
            "matched_batch_id": batch.batch_id,
            "s_db": 1,
            "s_rule": 0,
            "matched_record": matched_record,
        }

    # ── Step 4: Expiry matches → check for serial cloning ───────────────
    is_cloned = await check_serial_clone(
        session, extracted_gtin, extracted_batch_number
    )

    if is_cloned:
        return {
            "status": "FAILED",
            "reasons": [
                f"Serial scanned across multiple distinct facilities "
                f"(clone detected for GTIN {extracted_gtin}, "
                f"batch {extracted_batch_number})"
            ],
            "matched_batch_id": batch.batch_id,
            "s_db": 1,
            "s_rule": 50,
            "matched_record": matched_record,
        }

    # ── Step 5: Everything clean → PASSED ───────────────────────────────
    return {
        "status": "PASSED",
        "reasons": [],
        "matched_batch_id": batch.batch_id,
        "s_db": 1,
        "s_rule": 100,
        "matched_record": matched_record,
    }
