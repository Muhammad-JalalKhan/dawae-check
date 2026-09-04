"""AI Engine service – packaging image analysis (OCR + visual defect detection).

When MOCK_AI_ENGINE=true (default for dev), returns hardcoded Augmentin data
that matches the seed DB for easy end-to-end testing.

When MOCK_AI_ENGINE=false, calls a vision-language model (Qwen2.5-VL or any
OpenAI-compatible endpoint) via AsyncOpenAI for real OCR and defect detection.
"""

from __future__ import annotations

import base64
import json
import logging
import re

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
# Instructs the model to perform OCR token extraction AND physical print
# defect detection with bounding boxes on a 0–1000 normalized integer scale.

_VISION_PROMPT = """\
You are a pharmaceutical packaging inspection AI.
Analyze the provided macro photograph of medicine packaging and return ONLY valid JSON (no markdown, no commentary).

Your response MUST be a single JSON object with exactly this structure:
{
  "ocr": {
    "gtin": "<string: 14-digit GTIN barcode number, or empty string if not found>",
    "batch_number": "<string: batch/lot number printed on packaging, or empty string>",
    "expiry_date": "<string: expiry date in YYYY-MM-DD format, or empty string>",
    "drap_reg_number": "<string: DRAP registration number if visible, or empty string>"
  },
  "visual": {
    "print_quality_score": <integer 0-100: overall physical print quality score where 100 = perfect offset lithography, lower = more defects>,
    "detected_defects": [
      {
        "label": "<string: one of 'Digital Halftone Ink Dots Detected', 'Typography Edge Blur', 'Barcode Contrast Degradation', 'Color Logo Boundary Shift'>",
        "confidence": <float 0.0-1.0>,
        "bbox_2d": [<ymin>, <xmin>, <ymax>, <xmax>]
      }
    ]
  }
}

CRITICAL RULES for bbox_2d:
- Each coordinate (ymin, xmin, ymax, xmax) MUST be an INTEGER on a scale of 0 to 1000.
- The scale represents the image dimensions normalized to 1000: 0 = top/left edge, 1000 = bottom/right edge.
- ymin < ymax and xmin < xmax always.
- If no defects are detected, detected_defects must be an empty array [].

Inspect carefully for these physical print defect types:
1. Digital Halftone Ink Dots Detected — visible CMYK dithering dots typical of inkjet/laser prints (not offset lithography). Severe penalty.
2. Typography Edge Blur — blurred or fuzzy text edges, ink bleed on letter boundaries.
3. Barcode Contrast Degradation — low contrast, faded, or smeared barcode bars that would impair scanning.
4. Color Logo Boundary Shift — misaligned color registration, logo color bleeding, or boundary shift.

Score print_quality_score based on:
- Start at 100 (perfect offset lithography).
- Digital halftone dithering: subtract up to 45 points.
- Typography edge blur / ink bleed: subtract up to 25 points.
- Barcode contrast degradation: subtract up to 20 points.
- Color / logo boundary shift: subtract up to 15 points.

Return ONLY the raw JSON object. Do NOT wrap in markdown code blocks.
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


def _parse_model_response(raw: str) -> dict:
    """Parse the model's raw text response into a validated dict.

    Handles markdown fences, reasoning/thinking preamble, and provides a
    fallback error structure if parsing fails.
    """
    data = _extract_json(raw)

    if data is None:
        logger.error("Failed to extract JSON from AI response.\nRaw: %s", raw[:1000])
        # Fallback: return a safe structure so the pipeline doesn't crash
        return {
            "ocr": {
                "gtin": "",
                "batch_number": "",
                "expiry_date": "",
                "drap_reg_number": "",
            },
            "visual": {
                "print_quality_score": 0,
                "detected_defects": [],
            },
            "_parse_error": "No valid JSON object/array found in model response",
        }

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
            "gtin": str(ocr.get("gtin", "")),
            "batch_number": str(ocr.get("batch_number", "")),
            "expiry_date": str(ocr.get("expiry_date", "")),
            "drap_reg_number": str(ocr.get("drap_reg_number", "")),
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
            },
            "visual": {
                "print_quality_score": float (0-100),
                "detected_defects": [
                    {"label": str, "confidence": float, "bbox_2d": [ymin, xmin, ymax, xmax]},
                    ...
                ],
            }
        }
    """
    if settings.MOCK_AI_ENGINE:
        logger.info("MOCK_AI_ENGINE=true — returning hardcoded Augmentin mock payload")
        return _MOCK_RESPONSE.copy()

    # ── Live AI inference via OpenAI-compatible API ──────────────────────────
    logger.info(
        "MOCK_AI_ENGINE=false — calling live model '%s' at %s",
        settings.AI_MODEL_NAME,
        settings.DASHSCOPE_BASE_URL,
    )

    # Encode image to base64 data URI for the vision API
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    image_data_url = f"data:image/jpeg;base64,{b64_image}"

    client = _build_client()

    try:
        response = await client.chat.completions.create(
            model=settings.AI_MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url},
                        },
                        {
                            "type": "text",
                            "text": _VISION_PROMPT,
                        },
                    ],
                }
            ],
            temperature=0.1,
            max_tokens=2048,
        )
    except Exception as exc:
        logger.error("AI model API call failed: %s", exc)
        raise RuntimeError(f"AI model API call failed: {exc}") from exc

    # Extract raw text from the response
    raw_text = response.choices[0].message.content or ""
    logger.info("AI model raw response length: %d chars", len(raw_text))

    # Parse and validate the structured JSON response
    result = _parse_model_response(raw_text)

    if "_parse_error" in result:
        logger.warning("AI response had parse errors; returning safe fallback")

    logger.info(
        "AI analysis complete — OCR gtin=%s batch=%s expiry=%s | visual score=%.1f defects=%d",
        result["ocr"]["gtin"],
        result["ocr"]["batch_number"],
        result["ocr"]["expiry_date"],
        result["visual"]["print_quality_score"],
        len(result["visual"]["detected_defects"]),
    )

    return result
