"""AI Engine service – packaging image analysis (OCR + visual defect detection).

When MOCK_AI_ENGINE=true (default for dev), returns hardcoded Augmentin data
that matches the seed DB for easy end-to-end testing.

When MOCK_AI_ENGINE=false, delegates to the real Qwen2.5-VL pipeline
(placeholder raises NotImplementedError until the AI lead integrates it).
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("dawae-check.ai")


# ── Mock payload ─────────────────────────────────────────────────────────────
# Returns Augmentin 625mg data matching seed DB (gtin=08964000123456, batch=B492,
# expiry=2026-12-31) so the verify endpoint produces a GENUINE verdict in mock mode.

_MOCK_RESPONSE: dict = {
    "ocr": {
        "gtin": "08964000123456",
        "batch_number": "B492",
        "expiry_date": "2026-12-31",
        "drap_reg_number": "REG-PAK-00201",
    },
    "visual": {
        "print_quality_score": 72,
        "detected_defects": [
            {
                "label": "Minor Halftone Pattern",
                "confidence": 0.45,
                "bbox_2d": [100, 150, 300, 400],
            }
        ],
    },
}


async def analyze_packaging(image_bytes: bytes) -> dict:
    """Analyze a packaging image: OCR extraction + visual defect detection.

    Parameters
    ----------
    image_bytes : bytes
        Raw JPEG image bytes from the uploaded file.

    Returns
    -------
    dict
        Structure:
        {
            "ocr": {
                "gtin": str,
                "batch_number": str,
                "expiry_date": str (YYYY-MM-DD),
                "drap_reg_number": str,
            },
            "visual": {
                "print_quality_score": float (0-100),
                "detected_defects": [
                    {"label": str, "confidence": float, "bbox_2d": [x1,y1,x2,y2]},
                    ...
                ],
            }
        }

    Raises
    ------
    NotImplementedError
        When MOCK_AI_ENGINE=false and the real AI pipeline is not yet integrated.
    """
    if settings.MOCK_AI_ENGINE:
        logger.info("MOCK_AI_ENGINE=true — returning hardcoded Augmentin mock payload")
        return _MOCK_RESPONSE.copy()

    # ── Real AI engine placeholder ──────────────────────────────────────────
    # The AI teammate will replace this block with the actual Qwen2.5-VL
    # DashScope integration (OpenCV preprocessing + dual-pass prompting).
    raise NotImplementedError(
        "Real AI engine not yet integrated. "
        "Set MOCK_AI_ENGINE=true in .env for mock mode, "
        "or implement the Qwen2.5-VL pipeline here."
    )
