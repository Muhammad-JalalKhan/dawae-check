"""AI Engine service – packaging image analysis (OCR + visual defect detection).

When MOCK_AI_ENGINE=true (default for dev), returns hardcoded Augmentin data
that matches the seed DB for easy end-to-end testing.

When MOCK_AI_ENGINE=false, calls a vision-language model (Qwen-VL or any
OpenAI-compatible endpoint) via AsyncOpenAI for real OCR and defect detection.

This module performs NO database access. It returns the extracted OCR fields
(including the medicine ``brand_name``) to the caller, which decides how to
resolve them against the batch registry.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import traceback

from openai import AsyncOpenAI

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
        "brand_name": "Augmentin 14 Tablets",
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

# ── Vision prompt ────────────────────────────────────────────────────────────
# Sent as the SYSTEM message. Strict forensic instruction: aggressive OCR
# (batch/expiry on carton flaps and stamps) plus defect detection with tight
# bounding boxes around suspicious numbers and suspicious color tones.
# Missing OCR fields are returned as JSON null (handled by _ocr_str).

_VISION_PROMPT = """\
You are a senior forensic pharmaceutical packaging inspector. Inspect this real mobile-captured medicine package.

Perform two tasks:
1. OCR EXTRACTION:
   Extract the following fields from the packaging:
   - "brand_name": (e.g. "Augmentin", "C-Retard", "Adol", "Panadol")
   - "batch_number": Look at carton flaps, embossed stamps, or printed text labeled "Batch", "B.No", "Lot".
   - "expiry_date": Standardize to YYYY-MM-DD (or YYYY-MM). Look for "Exp", "Expiry", "Validity".
   - "gtin": 14-digit GS1 barcode number if visible, else null.
   - "drap_reg_number": DRAP / drug registration code if visible (labels like "DRAP", "Reg. No", "Regn. No"), else null.

2. FORENSIC DEFECT DETECTION & BOUNDING BOXES:
   Inspect the physical packaging closely:
   A. NUMBER & TYPOGRAPHY INTEGRITY: Inspect the printed batch number, manufacturing date, and expiry date. Check for fuzzy ink bleeding, inconsistent font weights, restamping, or manual alteration.
   B. COLOR TONE & PRINT QUALITY: Inspect the background color tone, branding panels, and logos. Check for uneven color gradients, faded hues, inkjet halftone dot dithering (cheap reprint), or color shifts compared to standard pharmaceutical cartons.

   If you find ANY defect or suspicious area (such as an altered number, blurry text, missing registration code, or abnormal color tone), you MUST add an entry to "detected_defects" with the exact 2D bounding box [ymin, xmin, ymax, xmax] on a normalized 0-1000 integer scale:
   - For suspicious numbers: draw the bounding box tightly around the batch or expiry digits.
   - For abnormal color tone: draw the bounding box over the suspicious colored panel or logo.

Return ONLY a valid JSON object matching this schema (no markdown, no extra text):
{
  "ocr": {
    "brand_name": "string or null",
    "batch_number": "string or null",
    "expiry_date": "YYYY-MM-DD or null",
    "gtin": "string or null",
    "drap_reg_number": "string or null"
  },
  "visual": {
    "print_quality_score": integer between 0 and 100,
    "detected_defects": [
      {
        "label": "Short description (e.g. 'Altered Expiry Typography' or 'Inconsistent Color Tone')",
        "confidence": float between 0.0 and 1.0,
        "bbox_2d": [ymin, xmin, ymax, xmax]
      }
    ]
  }
}

CRITICAL RULES for bbox_2d:
- Each coordinate (ymin, xmin, ymax, xmax) MUST be an INTEGER on a scale of 0 to 1000.
- 0 = top/left edge, 1000 = bottom/right edge of the image.
- ymin < ymax and xmin < xmax always.
- If no defects are detected, detected_defects must be an empty array [].

Scoring guidance (start at 100 = flawless factory offset lithography):
- Inkjet halftone dot dithering / cheap reprint: subtract up to 45 points.
- Fuzzy ink bleeding, inconsistent font weights, restamped or altered numbers: subtract up to 30 points.
- Uneven color gradients, faded hues, color shifts: subtract up to 25 points.
- Missing or suspicious registration code: subtract up to 20 points.

Return ONLY the raw JSON object now.
"""


def _strip_markdown_fence(raw: str) -> str:
    """Strip markdown code fences (```json ... ```) from model output."""
    text = raw.strip()
    # Remove opening fence: ```json or ``` or ```JSON
    text = re.sub(r"^```(?:json|JSON)?\s*\n?", "", text)
    # Remove closing fence
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _extract_json(text: str) -> dict | list | None:
    """Extract the first valid JSON object/array from a possibly noisy string.

    Some reasoning/thinking models emit preamble text (e.g. <thinking>...</thinking>
    or plain explanatory sentences) before the final JSON payload. This helper
    strips markdown fences and scans for the first balanced JSON structure.
    """
    text = _strip_markdown_fence(text)

    # Scan for the first JSON object '{' or array '[' and try to parse the
    # balanced substring starting there.
    for start_idx, char in enumerate(text):
        if char in ("{", "["):
            for end_idx in range(len(text), start_idx, -1):
                candidate = text[start_idx:end_idx]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

    return None


def _ocr_str(value: object) -> str:
    """Normalize an OCR field to a stripped string.

    The forensic prompt allows the model to return JSON ``null`` for fields it
    cannot read. Those must become empty strings (not the string ``"None"``)
    so downstream DB lookups treat them as missing.
    """
    if value is None:
        return ""
    return str(value).strip()


def _parse_model_response(raw: str) -> dict:
    """Parse the model's raw text response into a validated dict.

    Handles markdown fences and reasoning/thinking preamble. Raises ``ValueError``
    when no valid JSON object/array can be extracted — callers must NOT swallow
    this with a silent default score (see :func:`analyze_packaging`).
    """
    data = _extract_json(raw)

    if data is None:
        raise ValueError(
            "No valid JSON object/array found in model response. "
            f"Raw (first 1000 chars): {raw[:1000]!r}"
        )

    # If the model returned an array, wrap it in our expected object shape
    if isinstance(data, list):
        data = {"detected_defects": data}

    # Ensure top-level keys exist with safe defaults
    ocr = data.get("ocr", {}) if isinstance(data, dict) else {}
    visual = data.get("visual", {}) if isinstance(data, dict) else {}

    if not isinstance(ocr, dict):
        ocr = {}
    if not isinstance(visual, dict):
        visual = {}

    return {
        "ocr": {
            "gtin": _ocr_str(ocr.get("gtin")),
            "batch_number": _ocr_str(ocr.get("batch_number")),
            "expiry_date": _ocr_str(ocr.get("expiry_date")),
            "drap_reg_number": _ocr_str(ocr.get("drap_reg_number")),
            "brand_name": _ocr_str(ocr.get("brand_name")),
        },
        "visual": {
            "print_quality_score": float(visual.get("print_quality_score", 0)),
            "detected_defects": _validate_defects(visual.get("detected_defects", [])),
        },
    }


def _validate_defects(defects: list) -> list[dict]:
    """Validate and normalize detected_defects list."""
    validated = []
    for d in defects:
        if not isinstance(d, dict):
            continue
        bbox = d.get("bbox_2d", [])
        # Ensure bbox is 4 integers clamped to [0, 1000]
        if isinstance(bbox, list) and len(bbox) == 4:
            bbox = [max(0, min(1000, int(v))) for v in bbox]
        else:
            bbox = [0, 0, 0, 0]

        validated.append({
            "label": str(d.get("label", "Unknown Defect")),
            "confidence": max(0.0, min(1.0, float(d.get("confidence", 0.0)))),
            "bbox_2d": bbox,
        })
    return validated


def _build_client() -> AsyncOpenAI:
    """Build an AsyncOpenAI client from environment settings."""
    return AsyncOpenAI(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.DASHSCOPE_BASE_URL,
    )


async def analyze_packaging(image_bytes: bytes) -> dict:
    """Analyze a packaging image: OCR extraction + visual defect detection.

    Parameters
    ----------
    image_bytes : bytes
        Raw JPEG/PNG image bytes from the uploaded file.

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
                "brand_name": str,
            },
            "visual": {
                "print_quality_score": float (0-100),
                "detected_defects": [
                    {"label": str, "confidence": float, "bbox_2d": [ymin, xmin, ymax, xmax]},
                    ...
                ],
            }
        }

    Raises
    ------
    RuntimeError
        If the model API call fails or the response cannot be parsed as JSON.
        Failures are printed with a full traceback and NEVER masked with a
        default score.
    """
    if settings.MOCK_AI_ENGINE:
        logger.info("MOCK_AI_ENGINE=true — returning hardcoded Augmentin mock payload")
        return _MOCK_RESPONSE.copy()

    # ── Live AI inference via OpenAI-compatible API ──────────────────────────
    endpoint = settings.DASHSCOPE_BASE_URL
    model = settings.AI_MODEL_NAME
    # Verbose, always-on-console logging so test runs can see the exact call.
    print(f"[ai_engine] Calling vision endpoint: {endpoint}")
    print(f"[ai_engine] Using model: {model}")
    logger.info(
        "MOCK_AI_ENGINE=false — calling live model '%s' at %s",
        model,
        endpoint,
    )

    # Encode image to base64 data URI for the vision API
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    image_data_url = f"data:image/jpeg;base64,{b64_image}"

    client = _build_client()

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _VISION_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Analyze this packaging image and return the JSON "
                                "object now."
                            ),
                        },
                    ],
                },
            ],
            temperature=0.1,
            max_tokens=2048,
        )
    except Exception as exc:
        # Do NOT mask the error with a default score — print the full traceback.
        print(f"[ai_engine] AI model API call FAILED: {exc}")
        traceback.print_exc()
        logger.error("AI model API call failed: %s", exc, exc_info=True)
        raise RuntimeError(f"AI model API call failed: {exc}") from exc

    # Extract raw text from the response and print it BEFORE parsing.
    raw_text = response.choices[0].message.content or ""
    print("[ai_engine] ── RAW MODEL RESPONSE (pre-parse) " + "─" * 30)
    print(raw_text)
    print("[ai_engine] ── END RAW MODEL RESPONSE " + "─" * 37)
    logger.info("AI model raw response length: %d chars", len(raw_text))

    # Parse and validate the structured JSON response — loud on failure.
    try:
        result = _parse_model_response(raw_text)
    except Exception as exc:
        print(f"[ai_engine] JSON parsing FAILED: {exc}")
        traceback.print_exc()
        logger.error("Failed to parse AI model JSON response: %s", exc, exc_info=True)
        raise RuntimeError(f"Failed to parse AI model JSON response: {exc}") from exc

    logger.info(
        "AI analysis complete — OCR gtin=%s batch=%s expiry=%s brand=%s | visual score=%.1f defects=%d",
        result["ocr"]["gtin"],
        result["ocr"]["batch_number"],
        result["ocr"]["expiry_date"],
        result["ocr"]["brand_name"],
        result["visual"]["print_quality_score"],
        len(result["visual"]["detected_defects"]),
    )

    return result
