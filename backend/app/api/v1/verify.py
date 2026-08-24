"""POST /api/v1/verify-packaging — single-scan verification endpoint.

Accepts a multipart image upload, runs the dual-gate verification pipeline
(Layer-1 DB check + Layer-2 visual AI), computes the final score, persists
the result, and returns the full response contract.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.scanned_log import ScannedLog
from app.schemas import VerifyResponse, Layer1DatabaseCheck, Layer2VisualCheck
from app.services.ai_engine import analyze_packaging
from app.services.db_gate import check_database_gate
from app.services.scoring import compute_final_score

logger = logging.getLogger("dawae-check.verify")
router = APIRouter(tags=["verify"])


def _build_technical_summary(verdict: str, layer1: dict, layer2: dict) -> str:
    """Generate a human-readable technical summary string."""
    if verdict == "GENUINE":
        return (
            "Packaging passed both database and visual inspection. "
            "Batch is registered and print quality is within acceptable parameters."
        )
    parts: list[str] = []
    if layer1["status"] == "FAILED":
        parts.append(
            f"Database gate failed: {'; '.join(layer1['reasons'])}."
        )
    if layer2["status"] == "FAILED":
        defects = layer2.get("detected_defects", [])
        labels = [d["label"] for d in defects[:3]]
        parts.append(
            f"Visual inspection flagged: {', '.join(labels)}."
        )
    if not parts:
        parts.append("One or more verification layers flagged anomalies.")
    return " ".join(parts)


@router.post("/verify-packaging", response_model=VerifyResponse)
async def verify_packaging(
    file: UploadFile = File(..., description="3x macro packaging photo (JPEG)"),
    device_id: str = Form(..., description="Device identifier e.g. MOB-98421"),
    facility_id: str = Form(..., description="Facility identifier e.g. ALK-DISP-KHI-04"),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    session: AsyncSession = Depends(get_session),
):
    """Run dual-gate verification on an uploaded packaging image."""

    # 1. Generate unique request_id
    short_uuid = uuid.uuid4().hex[:8]
    request_id = f"req-{short_uuid}"

    # 2. Read image and call AI engine
    image_bytes = await file.read()
    try:
        ai_result = await analyze_packaging(image_bytes)
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    ocr = ai_result["ocr"]
    visual = ai_result["visual"]

    extracted_gtin: str = ocr.get("gtin", "")
    extracted_batch: str = ocr.get("batch_number", "")
    extracted_expiry: str = ocr.get("expiry_date", "")
    extracted_drap: str = ocr.get("drap_reg_number", "")

    # 3. Layer-1: database gate
    layer1_result = await check_database_gate(
        session=session,
        extracted_gtin=extracted_gtin,
        extracted_batch_number=extracted_batch,
        extracted_expiry=extracted_expiry,
        facility_id=facility_id,
        latitude=latitude,
        longitude=longitude,
    )

    s_db: int = layer1_result["s_db"]
    s_rule: int = layer1_result["s_rule"]

    # 4. Layer-2: visual score
    print_quality_score: float = float(visual.get("print_quality_score", 0))
    detected_defects: list[dict] = visual.get("detected_defects", [])
    s_visual: float = print_quality_score

    # Visual status: FAILED if score < 50 or defects with high confidence exist
    layer2_status = "PASSED"
    if print_quality_score < 50:
        layer2_status = "FAILED"
    elif any(d.get("confidence", 0) >= 0.8 for d in detected_defects):
        layer2_status = "FAILED"

    # 5. Compute final score
    authenticity_score, verdict = compute_final_score(s_db, s_rule, s_visual)

    # 6. Build response dicts
    layer1_response = {
        "status": layer1_result["status"],
        "reasons": layer1_result["reasons"],
        "matched_record": layer1_result["matched_record"],
    }

    layer2_response = {
        "status": layer2_status,
        "print_quality_score": print_quality_score,
        "detected_defects": detected_defects,
    }

    technical_summary = _build_technical_summary(
        verdict, layer1_result, {"status": layer2_status, "detected_defects": detected_defects}
    )

    # 7. Persist to scanned_logs
    expiry_date: date | None = None
    if extracted_expiry:
        try:
            expiry_date = date.fromisoformat(extracted_expiry)
        except ValueError:
            expiry_date = None

    log_entry = ScannedLog(
        request_id=request_id,
        device_id=device_id,
        facility_id=facility_id,
        matched_batch_id=layer1_result.get("matched_batch_id"),
        extracted_gtin=extracted_gtin or None,
        extracted_batch_number=extracted_batch or None,
        extracted_expiry=expiry_date,
        extracted_drap_reg=extracted_drap or None,
        layer1_status=layer1_result["status"],
        layer1_reasons=layer1_result["reasons"],
        layer2_status=layer2_status,
        layer2_print_score=Decimal(str(print_quality_score)),
        layer2_defects=detected_defects,
        authenticity_score=Decimal(str(authenticity_score)),
        verdict=verdict,
        latitude=latitude,
        longitude=longitude,
    )
    session.add(log_entry)
    await session.commit()

    logger.info("Scan %s persisted — verdict=%s score=%.2f", request_id, verdict, authenticity_score)

    # 8. Return response contract
    return VerifyResponse(
        request_id=request_id,
        verdict=verdict,
        authenticity_score=authenticity_score,
        layer1_database_check=Layer1DatabaseCheck(**layer1_response),
        layer2_visual_check=Layer2VisualCheck(**layer2_response),
        technical_summary=technical_summary,
    )
