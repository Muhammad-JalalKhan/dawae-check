"""Live AI inference test — sends an image through analyze_packaging() and prints the result.

Usage:
    cd backend/
    python test_ai_live.py [path_to_image]

If no image path is provided, a small synthetic test image is generated
(a colored rectangle with text) using Pillow.

Requires:
    - MOCK_AI_ENGINE=false in .env
    - DASHSCOPE_API_KEY set to a valid API key
    - DASHSCOPE_BASE_URL set to the model endpoint
    - AI_MODEL_NAME set to the model identifier
"""

import asyncio
import json
import os
import sys
import time

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(__file__))


def _generate_test_image() -> bytes:
    """Generate a small synthetic JPEG image for testing when no file is provided."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("ERROR: Pillow is not installed. Run: pip install pillow")
        sys.exit(1)

    # Create a simple image that resembles a medicine box label
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Draw a box outline
    draw.rectangle([50, 50, 750, 550], outline=(0, 0, 0), width=3)

    # Add text that mimics packaging info
    try:
        font = ImageFont.truetype("arial.ttf", 28)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except (OSError, IOError):
        font = ImageFont.load_default()
        font_small = font

    draw.text((80, 80), "AUGMENTIN 625mg", fill=(0, 0, 0), font=font)
    draw.text((80, 130), "Amoxicillin/Clavulanic Acid", fill=(50, 50, 50), font=font_small)
    draw.text((80, 180), "GTIN: 08964000123456", fill=(0, 0, 0), font=font_small)
    draw.text((80, 220), "Batch: B492", fill=(0, 0, 0), font=font_small)
    draw.text((80, 260), "Exp: 2026-12-31", fill=(0, 0, 0), font=font_small)
    draw.text((80, 300), "DRAP Reg: REG-PAK-00201", fill=(0, 0, 0), font=font_small)

    # Draw a fake barcode area
    for i in range(20):
        x = 80 + i * 8
        draw.rectangle([x, 400, x + 4, 480], fill=(0, 0, 0))

    draw.text((80, 500), "Manufactured by: GSK Pakistan", fill=(100, 100, 100), font=font_small)

    # Save to bytes
    import io
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


async def run_test(image_path: str | None = None) -> None:
    """Run the live AI inference test."""
    from app.core.config import settings

    print("=" * 70)
    print("Dawae-Check — Live AI Inference Test")
    print("=" * 70)
    print(f"  MOCK_AI_ENGINE  : {settings.MOCK_AI_ENGINE}")
    print(f"  AI_MODEL_NAME   : {settings.AI_MODEL_NAME}")
    print(f"  DASHSCOPE_BASE  : {settings.DASHSCOPE_BASE_URL}")
    print(f"  API_KEY present : {'Yes' if settings.DASHSCOPE_API_KEY else 'No (EMPTY!)'}")
    print("=" * 70)

    if settings.MOCK_AI_ENGINE:
        print("\nWARNING: MOCK_AI_ENGINE=true — the test will return hardcoded mock data.")
        print("Set MOCK_AI_ENGINE=false in .env to test the live AI model.\n")

    if not settings.DASHSCOPE_API_KEY:
        print("\nERROR: DASHSCOPE_API_KEY is empty. Set it in your .env file.")
        sys.exit(1)

    # Load or generate image
    if image_path and os.path.isfile(image_path):
        print(f"\nLoading image from: {image_path}")
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        print(f"  Image size: {len(image_bytes):,} bytes")
    else:
        if image_path:
            print(f"\nWARNING: File not found: {image_path}")
        print("\nNo image provided — generating synthetic test image...")
        image_bytes = _generate_test_image()
        print(f"  Synthetic image size: {len(image_bytes):,} bytes")

    # Call the AI engine
    print("\nCalling analyze_packaging() ...")
    print("-" * 70)

    from app.services.ai_engine import analyze_packaging

    start_time = time.perf_counter()
    try:
        result = await analyze_packaging(image_bytes)
    except NotImplementedError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    except RuntimeError as exc:
        print(f"ERROR: AI model API call failed:\n  {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Unexpected exception: {type(exc).__name__}: {exc}")
        sys.exit(1)
    elapsed = time.perf_counter() - start_time

    # Pretty-print the result
    print(f"\nAPI response latency: {elapsed:.2f} seconds")

    print("\nStructured JSON Response:")
    print("-" * 70)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Validate structure
    print("\n" + "-" * 70)
    print("Structure Validation:")

    errors = []

    # Check OCR keys
    ocr = result.get("ocr", {})
    for key in ("gtin", "batch_number", "expiry_date", "drap_reg_number"):
        if key not in ocr:
            errors.append(f"Missing ocr.{key}")
        else:
            print(f"  ocr.{key:<20} = {ocr[key]!r}")

    # Check visual keys
    visual = result.get("visual", {})
    if "print_quality_score" not in visual:
        errors.append("Missing visual.print_quality_score")
    else:
        score = visual["print_quality_score"]
        print(f"  visual.print_quality_score = {score}")
        if not (0 <= score <= 100):
            errors.append(f"print_quality_score {score} out of range [0, 100]")

    defects = visual.get("detected_defects", [])
    print(f"  visual.detected_defects  = {len(defects)} defect(s)")

    for i, d in enumerate(defects):
        bbox = d.get("bbox_2d", [])
        print(f"    [{i}] label={d.get('label')!r}  confidence={d.get('confidence')}  bbox_2d={bbox}")

        # Validate bbox
        if len(bbox) != 4:
            errors.append(f"defect[{i}].bbox_2d has {len(bbox)} elements (expected 4)")
        elif not all(isinstance(v, int) and 0 <= v <= 1000 for v in bbox):
            errors.append(f"defect[{i}].bbox_2d values must be integers in [0, 1000]")
        elif not (bbox[0] < bbox[2] and bbox[1] < bbox[3]):
            errors.append(f"defect[{i}].bbox_2d: ymin must be < ymax and xmin must be < xmax")

    if errors:
        print(f"\n  VALIDATION ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    - {e}")
    else:
        print("\n  All structure checks PASSED")

    print("\nLatency assessment:")
    if elapsed > 6.0:
        print(f"  SLOW: {elapsed:.2f}s exceeds the 5-6s demo target. Consider qwen-vl-plus or a non-thinking model.")
    elif elapsed > 4.0:
        print(f"  OKAY: {elapsed:.2f}s is acceptable but on the slower side for a live demo.")
    else:
        print(f"  GOOD: {elapsed:.2f}s is well within the live demo target.")

    print("\n" + "=" * 70)
    print("Test complete.")
    print("=" * 70)


if __name__ == "__main__":
    image_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_test(image_arg))
