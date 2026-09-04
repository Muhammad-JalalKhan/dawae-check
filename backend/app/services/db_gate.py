"""DB Gate service – Layer-1 batch lookup, expiry verification, and clone detection.

Performs a deterministic database gate check:
1. Look up batch_registry using the GTIN and/or batch number. The DRAP
   registration number is NOT required to be printed on the carton flap.
2. If no match → FAILED (unregistered batch).
3. If match but expiry unreadable/mismatch → FAILED (expiry rule).
4. If a printed DRAP contradicts the registry → FAILED (DRAP mismatch).
   A missing DRAP is inferred from the registry (INFERRED_FROM_REGISTRY);
   a matching printed DRAP is VERIFIED_MATCH.
5. If match and expiry matches → run clone detection.
   5a. Clone detected → FAILED (cloned serial), s_rule=50.
   5b. No clone → PASSED, s_rule=100.

This is an isolated function so the gate logic can be swapped later.
"""

import logging
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch_registry import BatchRegistry
from app.services.clone_detection import check_serial_clone

logger = logging.getLogger("dawae-check.db-gate")


def _drap_matches(scanned: str, official: str) -> bool:
    """Tolerantly compare a scanned DRAP number with the registry value.

    Cartons often print only the numeric part of the registration code
    (e.g. '00201' against a registry 'REG-PAK-00201') and OCR can drop
    dashes and spaces. Both sides are normalised to upper-case
    alphanumerics; equality or either-side containment counts as a match.
    """
    def normalize(value: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", value.upper())

    a, b = normalize(scanned), normalize(official)
    if not a or not b:
        return False
    if a == b:
        return True
    # Tolerate the carton printing only part of the registration code.
    if len(a) >= 4 and len(b) >= 4:
        return a in b or b in a
    return False


async def check_database_gate(
    session: AsyncSession,
    extracted_gtin: str,
    extracted_batch_number: str,
    extracted_expiry: str | date,
    facility_id: str,
    latitude: float | None = None,
    longitude: float | None = None,
    extracted_brand_name: str = "",
    extracted_drap: str = "",
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
        Expiry date extracted from the medicine image / OCR. Accepts
        ``YYYY-MM-DD`` or partial ``YYYY-MM`` strings, or a ``date`` object.
        A partial YYYY-MM value is compared by year and month.
    facility_id : str
        Identifier of the facility performing the scan.
    latitude, longitude : float | None
        Optional GPS coordinates of the scan location (reserved for future use).
    extracted_brand_name : str
        Medicine brand name read by OCR. Used only as a fuzzy fallback to
        resolve the active batch when the GTIN/batch codes could not be read.
    extracted_drap : str
        DRAP registration number printed on the packaging, if any. A missing
        DRAP is not an error — the registry value is used instead
        (``INFERRED_FROM_REGISTRY``). A printed DRAP only fails the gate
        when it explicitly contradicts the registry (``MISMATCH``); a match
        is reported as ``VERIFIED_MATCH``.

    Returns
    -------
    dict
        Keys: ``status``, ``reasons``, ``matched_batch_id``, ``s_db``,
        ``s_rule``, ``matched_record``.
    """

    # Normalise OCR inputs — the vision model can return empty/missing
    # values when the packaging text is unreadable.
    extracted_gtin = (extracted_gtin or "").strip()
    extracted_batch_number = (extracted_batch_number or "").strip()
    extracted_brand_name = (extracted_brand_name or "").strip()
    extracted_drap = (extracted_drap or "").strip()

    # Normalise extracted_expiry for comparison.
    # An unreadable / missing / malformed expiry stays None instead of
    # crashing the gate with a ValueError. The vision model may return a
    # partial "YYYY-MM" when the carton only prints month/year — keep that
    # as (year, month) so it can still be compared against the registry.
    expiry_date: date | None = None
    expiry_ym: tuple[int, int] | None = None
    if isinstance(extracted_expiry, date):
        expiry_date = extracted_expiry
    elif extracted_expiry:
        text = str(extracted_expiry).strip()
        try:
            expiry_date = date.fromisoformat(text)
        except ValueError:
            partial = re.fullmatch(r"(\d{4})-(\d{2})", text)
            if partial:
                year, month = int(partial.group(1)), int(partial.group(2))
                if 1 <= month <= 12:
                    expiry_ym = (year, month)

    # ── Step 1: Look up batch_registry by GTIN and/or batch number ─────
    batch: BatchRegistry | None = None

    if extracted_gtin and extracted_batch_number:
        # Both codes read: require the exact (gtin, batch) pair.
        stmt = select(BatchRegistry).where(
            BatchRegistry.gtin == extracted_gtin,
            BatchRegistry.batch_number == extracted_batch_number,
        )
        batch = (await session.execute(stmt)).scalar_one_or_none()
    elif extracted_gtin or extracted_batch_number:
        # Only one code readable: resolve the single active batch carrying
        # that code. Multiple active candidates are ambiguous — not trusted.
        code_field = (
            BatchRegistry.gtin if extracted_gtin else BatchRegistry.batch_number
        )
        code_value = extracted_gtin or extracted_batch_number
        stmt = select(BatchRegistry).where(
            BatchRegistry.is_active.is_(True),
            code_field == code_value,
        )
        rows = (await session.execute(stmt)).scalars().all()
        if len(rows) == 1:
            batch = rows[0]
            extracted_gtin = batch.gtin
            extracted_batch_number = batch.batch_number
            logger.info(
                "Single-code lookup resolved %s '%s' -> batch %s/%s",
                "GTIN" if code_field is BatchRegistry.gtin else "batch number",
                code_value,
                batch.gtin,
                batch.batch_number,
            )

    # Fuzzy brand fallback: only when OCR could not read a usable GTIN/batch
    # (at least one is empty) but did read a brand name. A single active batch
    # for that brand lets the gate proceed instead of hard-failing on unreadable
    # codes; multiple active batches are treated as ambiguous and ignored.
    if (
        batch is None
        and extracted_brand_name
        and (not extracted_gtin or not extracted_batch_number)
    ):
        fuzzy_stmt = select(BatchRegistry).where(
            BatchRegistry.is_active.is_(True),
            BatchRegistry.brand_name.ilike(f"%{extracted_brand_name}%"),
        )
        rows = (await session.execute(fuzzy_stmt)).scalars().all()
        if len(rows) == 1:
            batch = rows[0]
            extracted_gtin = batch.gtin
            extracted_batch_number = batch.batch_number
            if expiry_date is None and expiry_ym is None:
                expiry_date = batch.official_expiry
            logger.info(
                "Fuzzy brand fallback matched '%s' -> batch %s/%s",
                extracted_brand_name,
                batch.gtin,
                batch.batch_number,
            )
        elif len(rows) > 1:
            logger.info(
                "Fuzzy brand fallback for '%s' matched %d active batches "
                "(ambiguous) - not trusting brand-only match",
                extracted_brand_name,
                len(rows),
            )

    # ── Step 2: No match → FAILED, unregistered batch ───────────────────
    if batch is None:
        reasons = ["Unregistered batch"]
        if not extracted_gtin or not extracted_batch_number:
            reasons.append(
                "OCR could not read a GTIN or batch number from the image"
            )
        return {
            "status": "FAILED",
            "reasons": reasons,
            "matched_batch_id": None,
            "s_db": 0,
            "s_rule": 0,
            "matched_record": None,
        }

    # DRAP resolution: the registration number is frequently not printed on
    # carton flaps. A missing scanned DRAP is fine — the registry record
    # supplies the verified registration (INFERRED_FROM_REGISTRY). A printed
    # DRAP only fails the gate when it contradicts the registry (below).
    if extracted_drap:
        drap_status = (
            "VERIFIED_MATCH"
            if _drap_matches(extracted_drap, batch.drap_reg_number)
            else "MISMATCH"
        )
    else:
        drap_status = "INFERRED_FROM_REGISTRY"

    # Build matched_record helper (includes the verified/inferred DRAP)
    matched_record = {
        "gtin": batch.gtin,
        "brand_name": batch.brand_name,
        "batch_number": batch.batch_number,
        "official_expiry": str(batch.official_expiry),
        "drap_reg_number": batch.drap_reg_number,
        "drap_status": drap_status,
    }

    # ── Step 3: Expiry unreadable or mismatch → FAILED ────────────────────────────────
    if expiry_date is None and expiry_ym is None:
        return {
            "status": "FAILED",
            "reasons": [
                "Expiry date unreadable — cannot be confirmed against the official registry"
            ],
            "matched_batch_id": batch.batch_id,
            "s_db": 1,
            "s_rule": 0,
            "matched_record": matched_record,
        }

    if expiry_date is not None:
        expiry_matches = expiry_date == batch.official_expiry
        extracted_desc = str(expiry_date)
    else:
        expiry_matches = expiry_ym == (
            batch.official_expiry.year,
            batch.official_expiry.month,
        )
        extracted_desc = f"{expiry_ym[0]:04d}-{expiry_ym[1]:02d}"

    if not expiry_matches:
        return {
            "status": "FAILED",
            "reasons": [
                f"Expiry mismatch: extracted {extracted_desc} vs official {batch.official_expiry}"
            ],
            "matched_batch_id": batch.batch_id,
            "s_db": 1,
            "s_rule": 0,
            "matched_record": matched_record,
        }

    # Printed DRAP explicitly contradicts the registry → FAILED. A missing
    # DRAP (INFERRED_FROM_REGISTRY) never reaches this branch.
    if drap_status == "MISMATCH":
        return {
            "status": "FAILED",
            "reasons": [
                "DRAP registration mismatch: extracted "
                f"{extracted_drap} vs official {batch.drap_reg_number}"
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
