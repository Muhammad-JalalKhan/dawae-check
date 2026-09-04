import os
import json
import math
import random
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "dataset"
ZIP_OUTPUT_PATH = BASE_DIR / "demo_dataset.zip"

IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 960

# Palette Definitions
COLOR_BG_CARD = (248, 249, 250)
COLOR_TEXT_DARK = (20, 24, 33)
COLOR_TEXT_MUTED = (90, 100, 115)
COLOR_BORDER = (215, 222, 230)
COLOR_GS1_ACCENT = (13, 148, 136)   # Teal Brand Accent
COLOR_WARN_RED = (220, 38, 38)
COLOR_GSK_ORANGE = (235, 110, 30)
COLOR_PFIZER_BLUE = (0, 122, 255)
COLOR_ABBOTT_RED = (227, 24, 55)

def get_scaled_font(size: int):
    """
    Attempts to load standard TrueType fonts available on Windows/Linux;
    falls back safely to default bitmap font if not present.
    """
    candidate_fonts = [
        "arial.ttf",
        "segoeui.ttf",
        "DejaVuSans.ttf",
        "LiberationSans-Regular.ttf",
        "NotoSans-Regular.ttf"
    ]
    for font_name in candidate_fonts:
        try:
            return ImageFont.truetype(font_name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()

def draw_header_banner(draw: ImageDraw.ImageDraw, brand_name: str, generic_name: str, color_accent: tuple):
    """Draws upper packaging branding banner with industrial clean margins."""
    draw.rectangle([(0, 0), (IMAGE_WIDTH, 140)], fill=color_accent)
    draw.rectangle([(0, 140), (IMAGE_WIDTH, 148)], fill=(0, 0, 0, 40))
    
    font_brand = get_scaled_font(52)
    font_generic = get_scaled_font(26)
    
    draw.text((60, 28), brand_name, fill=(255, 255, 255), font=font_brand)
    draw.text((64, 94), generic_name, fill=(240, 245, 250), font=font_generic)

def draw_simulated_datamatrix(draw: ImageDraw.ImageDraw, origin_x: int, origin_y: int, size: int, degradation: float = 0.0):
    """
    Draws an authentic 2D DataMatrix code visual with finder pattern
    and pseudo-random data modules. Includes degradation simulation for fake samples.
    """
    modules = 18
    mod_size = size // modules
    
    # Background quiet zone
    draw.rectangle(
        [(origin_x - 12, origin_y - 12), (origin_x + size + 12, origin_y + size + 12)],
        fill=(255, 255, 255),
        outline=(220, 225, 230),
        width=1
    )
    
    # Seed fixed matrix pattern
    random.seed(42)
    matrix = [[random.choice([0, 1]) for _ in range(modules)] for _ in range(modules)]
    
    # L-shaped solid finder pattern (left and bottom)
    for i in range(modules):
        matrix[i][0] = 1
        matrix[modules - 1][i] = 1
        # Alternating clock track (top and right)
        matrix[0][i] = 1 if (i % 2 == 0) else 0
        matrix[i][modules - 1] = 1 if (i % 2 == 0) else 0

    for r in range(modules):
        for c in range(modules):
            if matrix[r][c] == 1:
                mx = origin_x + (c * mod_size)
                my = origin_y + (r * mod_size)
                
                if degradation > 0 and random.random() < degradation:
                    # Simulated faded module or droplet noise
                    fill_color = (130, 130, 130)
                else:
                    fill_color = (20, 25, 30)
                    
                draw.rectangle([(mx, my), (mx + mod_size - 1, my + mod_size - 1)], fill=fill_color)

def apply_cmyk_halftone_dithering(img: Image.Image, intensity: float = 0.35) -> Image.Image:
    """
    Overlays CMYK color halftone dithering dot clusters across packaging surfaces
    to simulate low-grade desktop inkjet or digital commercial re-printing.
    """
    img_rgba = img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    step = 6
    cmyk_colors = [
        (0, 160, 230, 120),   # Cyan dot
        (230, 0, 125, 120),   # Magenta dot
        (240, 220, 0, 130),   # Yellow dot
        (30, 30, 30, 90)      # Key/Black dot
    ]
    
    random.seed(101)
    for y in range(160, IMAGE_HEIGHT - 60, step):
        for x in range(60, IMAGE_WIDTH - 60, step):
            if random.random() < intensity:
                color = random.choice(cmyk_colors)
                offset_x = random.randint(-1, 1)
                offset_y = random.randint(-1, 1)
                radius = random.choice([1, 2])
                overlay_draw.ellipse(
                    [(x + offset_x, y + offset_y), (x + offset_x + radius, y + offset_y + radius)],
                    fill=color
                )
                
    combined = Image.alpha_composite(img_rgba, overlay)
    # Slight blur to simulate inkjet fiber bleeding
    return combined.filter(ImageFilter.GaussianBlur(radius=0.7)).convert("RGB")

def generate_sample_augmentin_genuine() -> Image.Image:
    """
    Sample 1: Authentic Augmentin 625mg carton with industrial offset print.
    Razor-sharp typography, perfect contrast DataMatrix, and clean DRAP serialization.
    """
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), COLOR_BG_CARD)
    draw = ImageDraw.Draw(img)
    
    # Upper Branding Banner
    draw_header_banner(draw, "Augmentin 625mg", "Co-Amoxiclav (Amoxicillin & Clavulanic Acid)", COLOR_GSK_ORANGE)
    
    # Dosage & Pack Info Box
    draw.rectangle([(60, 180), (740, 520)], fill=(255, 255, 255), outline=COLOR_BORDER, width=2)
    font_bold = get_scaled_font(34)
    font_body = get_scaled_font(24)
    font_mono = get_scaled_font(26)
    
    draw.text((90, 210), "14 Film-coated Tablets (2 x 7)", fill=COLOR_TEXT_DARK, font=font_bold)
    draw.text((90, 260), "Each film-coated tablet contains:", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((90, 298), "* Amoxicillin Trihydrate Eq. to Amoxicillin ... 500 mg", fill=COLOR_TEXT_DARK, font=font_body)
    draw.text((90, 336), "* Potassium Clavulanate Eq. to Clavulanic Acid ... 125 mg", fill=COLOR_TEXT_DARK, font=font_body)
    draw.text((90, 388), "Keep out of the reach and sight of children.", fill=COLOR_WARN_RED, font=font_body)
    draw.text((90, 426), "Store below 25 deg C in a dry place protected from light.", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((90, 464), "DRAP Registration No: 00201 (GlaxoSmithKline Pakistan Ltd)", fill=COLOR_GS1_ACCENT, font=font_body)
    
    # 2D DataMatrix Serialization Zone
    draw.rectangle([(800, 180), (1220, 520)], fill=(255, 255, 255), outline=COLOR_BORDER, width=2)
    draw_simulated_datamatrix(draw, 840, 220, 260, degradation=0.0)
    
    # Regulatory Data Box (GTIN, Batch, Expiry)
    draw.rectangle([(60, 560), (1220, 880)], fill=(255, 255, 255), outline=COLOR_GS1_ACCENT, width=3)
    draw.rectangle([(60, 560), (1220, 620)], fill=COLOR_GS1_ACCENT)
    font_banner = get_scaled_font(28)
    draw.text((90, 574), "GS1 AUTHORITATIVE PRODUCT SERIALIZATION LOG", fill=(255, 255, 255), font=font_banner)
    
    draw.text((90, 650), "GLOBAL TRADE ITEM NUMBER (GTIN):", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 646), "08964000123456", fill=COLOR_TEXT_DARK, font=font_bold)
    
    draw.text((90, 706), "MANUFACTURER LOT / BATCH NUMBER:", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 702), "B492", fill=(13, 148, 136), font=font_bold)
    
    draw.text((90, 762), "OFFICIAL EXPIRATION DATE:", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 758), "2026-12-31  (VALID REGISTERED BATCH)", fill=(22, 163, 74), font=font_bold)
    
    draw.text((90, 818), "PRODUCTION PRINT METHOD:", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 814), "High-Speed Industrial Offset Lithography (Passed)", fill=COLOR_TEXT_DARK, font=font_mono)
    
    return img

def generate_sample_panadol_expiry_mismatch() -> Image.Image:
    """
    Sample 2: Panadol Extra with genuine packaging cardstock, but showing
    tampered/re-stamped expiry date (scratched original date + mismatched restamp).
    """
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), COLOR_BG_CARD)
    draw = ImageDraw.Draw(img)
    
    # Upper Branding Banner
    draw_header_banner(draw, "Panadol Extra", "Paracetamol 500mg + Caffeine 65mg (Haleon / GSK)", COLOR_PFIZER_BLUE)
    
    # Dosage & Info Box
    draw.rectangle([(60, 180), (740, 520)], fill=(255, 255, 255), outline=COLOR_BORDER, width=2)
    font_bold = get_scaled_font(34)
    font_body = get_scaled_font(24)
    font_mono = get_scaled_font(28)
    
    draw.text((90, 210), "40 Caplets (Tough on Pain)", fill=COLOR_TEXT_DARK, font=font_bold)
    draw.text((90, 264), "Effective relief from headache, migraine, backache,", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((90, 302), "toothache, rheumatic and period pain.", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((90, 360), "Active Ingredients per caplet:", fill=COLOR_TEXT_DARK, font=font_body)
    draw.text((90, 398), "* Paracetamol 500 mg", fill=COLOR_TEXT_DARK, font=font_body)
    draw.text((90, 436), "* Caffeine 65 mg", fill=COLOR_TEXT_DARK, font=font_body)
    draw.text((90, 474), "DRAP Registration No: 001842", fill=COLOR_TEXT_MUTED, font=font_body)
    
    # 2D DataMatrix Zone
    draw.rectangle([(800, 180), (1220, 520)], fill=(255, 255, 255), outline=COLOR_BORDER, width=2)
    draw_simulated_datamatrix(draw, 840, 220, 260, degradation=0.05)
    
    # Tampered Serialization Zone
    draw.rectangle([(60, 560), (1220, 880)], fill=(255, 255, 255), outline=COLOR_WARN_RED, width=3)
    draw.rectangle([(60, 560), (1220, 620)], fill=COLOR_WARN_RED)
    font_banner = get_scaled_font(28)
    draw.text((90, 574), "PACKAGING EXPIRATION INSPECTION ZONE (WARNING)", fill=(255, 255, 255), font=font_banner)
    
    draw.text((90, 650), "GLOBAL TRADE ITEM NUMBER (GTIN):", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 646), "08964000654321", fill=COLOR_TEXT_DARK, font=font_bold)
    
    draw.text((90, 706), "MANUFACTURER BATCH NUMBER:", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 702), "P811", fill=COLOR_TEXT_DARK, font=font_bold)
    
    # Simulate Date Tampering (Scratched old date + fraudulent bold restamp)
    draw.text((90, 762), "OFFICIAL DRAP REGISTERED EXPIRY:", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 758), "2025-06-30  (ORIGINAL RECORD)", fill=COLOR_TEXT_MUTED, font=font_bold)
    
    # Highlight physical stamp alteration
    draw.rectangle([(530, 804), (1180, 866)], fill=(254, 242, 242), outline=COLOR_WARN_RED, width=2)
    draw.text((90, 822), "PHYSICAL PRINTED EXPIRY ON BOX:", fill=COLOR_WARN_RED, font=font_bold)
    draw.text((540, 818), "2027-12-31  [TAMPERED RESTAMP]", fill=COLOR_WARN_RED, font=font_bold)
    
    # Visual scratch-off marks over the 2025 area
    for _ in range(12):
        x1 = random.randint(535, 780)
        y1 = random.randint(758, 785)
        draw.line([(x1, y1), (x1 + random.randint(8, 25), y1 + random.randint(-3, 3))], fill=(180, 50, 50), width=2)
        
    return img

def generate_sample_brufen_fake_halftone() -> Image.Image:
    """
    Sample 3: Brufen 400mg counterfeit reprint produced on commercial inkjet printer.
    Exhibits prominent CMYK halftone dithering dots, fuzzy typography edges,
    and blurred DataMatrix modules.
    """
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), COLOR_BG_CARD)
    draw = ImageDraw.Draw(img)
    
    # Upper Branding Banner
    draw_header_banner(draw, "Brufen 400mg", "Ibuprofen BP (Abbott Laboratories Pakistan)", COLOR_ABBOTT_RED)
    
    # Dosage & Info Box
    draw.rectangle([(60, 180), (740, 520)], fill=(255, 255, 255), outline=COLOR_BORDER, width=2)
    font_bold = get_scaled_font(34)
    font_body = get_scaled_font(24)
    
    draw.text((90, 210), "30 Sugar-coated Tablets", fill=COLOR_TEXT_DARK, font=font_bold)
    draw.text((90, 264), "Analgesic, Anti-inflammatory and Antipyretic", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((90, 310), "Formula: Each tablet contains Ibuprofen 400mg", fill=COLOR_TEXT_DARK, font=font_body)
    draw.text((90, 360), "Dosage: As directed by the registered medical practitioner.", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((90, 404), "Store in a cool and dry place below 30 deg C.", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((90, 450), "DRAP Registration No: 000412", fill=COLOR_TEXT_DARK, font=font_body)
    
    # Degraded 2D DataMatrix Zone
    draw.rectangle([(800, 180), (1220, 520)], fill=(255, 255, 255), outline=COLOR_BORDER, width=2)
    draw_simulated_datamatrix(draw, 840, 220, 260, degradation=0.25)
    
    # Serialization Box
    draw.rectangle([(60, 560), (1220, 880)], fill=(255, 255, 255), outline=(217, 119, 6), width=3)
    draw.rectangle([(60, 560), (1220, 620)], fill=(217, 119, 6))
    font_banner = get_scaled_font(28)
    draw.text((90, 574), "MICRO-PRINT FORENSICS EVALUATION ZONE (DEFECTIVE)", fill=(255, 255, 255), font=font_banner)
    
    draw.text((90, 650), "GLOBAL TRADE ITEM NUMBER (GTIN):", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 646), "08964000987654", fill=COLOR_TEXT_DARK, font=font_bold)
    
    draw.text((90, 706), "MANUFACTURER BATCH NUMBER:", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 702), "BR204  (VALID DB RECORD, FAKE PHYSICAL PRINT)", fill=(217, 119, 6), font=font_bold)
    
    draw.text((90, 762), "PRINTED EXPIRATION DATE:", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 758), "2026-08-31", fill=COLOR_TEXT_DARK, font=font_bold)
    
    draw.text((90, 818), "DETECTED PRINT DEFECT ARTIFACTS:", fill=COLOR_WARN_RED, font=font_body)
    draw.text((540, 814), "CMYK Halftone Inkjet Dithering Dots & Edge Bleeding", fill=COLOR_WARN_RED, font=font_bold)
    
    # Apply synthetic CMYK halftone dithering clusters
    halftoned_img = apply_cmyk_halftone_dithering(img, intensity=0.45)
    return halftoned_img

def generate_sample_arinac_unregistered() -> Image.Image:
    """
    Sample 4: Arinac Forte unregistered/counterfeit carton.
    Batch number AR999 is fabricated and absent from official Supabase registry,
    triggering Layer 1 deterministic gate rejection.
    """
    img = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), COLOR_BG_CARD)
    draw = ImageDraw.Draw(img)
    
    # Upper Branding Banner
    draw_header_banner(draw, "Arinac Forte", "Ibuprofen 400mg + Pseudoephedrine HCl 60mg", (100, 30, 140))
    
    # Dosage & Info Box
    draw.rectangle([(60, 180), (740, 520)], fill=(255, 255, 255), outline=COLOR_BORDER, width=2)
    font_bold = get_scaled_font(34)
    font_body = get_scaled_font(24)
    
    draw.text((90, 210), "100 Tablets (Cold & Flu Relief)", fill=COLOR_TEXT_DARK, font=font_bold)
    draw.text((90, 264), "For relief of symptoms associated with common cold,", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((90, 302), "sinusitis and allergic rhinitis.", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((90, 360), "Each film-coated tablet contains:", fill=COLOR_TEXT_DARK, font=font_body)
    draw.text((90, 398), "* Ibuprofen ... 400 mg", fill=COLOR_TEXT_DARK, font=font_body)
    draw.text((90, 436), "* Pseudoephedrine Hydrochloride ... 60 mg", fill=COLOR_TEXT_DARK, font=font_body)
    draw.text((90, 474), "Unverified DRAP Registration: REG-PAK-99999", fill=COLOR_WARN_RED, font=font_body)
    
    # 2D DataMatrix Zone
    draw.rectangle([(800, 180), (1220, 520)], fill=(255, 255, 255), outline=COLOR_BORDER, width=2)
    draw_simulated_datamatrix(draw, 840, 220, 260, degradation=0.15)
    
    # Serialization Box
    draw.rectangle([(60, 560), (1220, 880)], fill=(255, 255, 255), outline=COLOR_WARN_RED, width=3)
    draw.rectangle([(60, 560), (1220, 620)], fill=COLOR_WARN_RED)
    font_banner = get_scaled_font(28)
    draw.text((90, 574), "REGULATORY BATCH VERIFICATION AUDIT (HARD REJECTION)", fill=(255, 255, 255), font=font_banner)
    
    draw.text((90, 650), "GLOBAL TRADE ITEM NUMBER (GTIN):", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 646), "08964000112233  [UNREGISTERED]", fill=COLOR_WARN_RED, font=font_bold)
    
    draw.text((90, 706), "MANUFACTURER LOT / BATCH NUMBER:", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 702), "AR999  (ABSENT FROM OFFICIAL DRAP REGISTRY)", fill=COLOR_WARN_RED, font=font_bold)
    
    draw.text((90, 762), "PRINTED EXPIRATION DATE:", fill=COLOR_TEXT_MUTED, font=font_body)
    draw.text((540, 758), "2025-11-30", fill=COLOR_TEXT_MUTED, font=font_bold)
    
    draw.text((90, 818), "DETERMINISTIC VERDICT ENGINE:", fill=COLOR_WARN_RED, font=font_body)
    draw.text((540, 814), "S_DB = 0 -> Authenticity Score = 0.0% (COUNTERFEIT)", fill=COLOR_WARN_RED, font=font_bold)
    
    return img

def build_dataset_manifest() -> dict:
    """Constructs the canonical JSON manifest index matching project specifications."""
    return {
        "project": "Dawae-Check Validation Dataset",
        "version": "1.0.0",
        "capture_specifications": {
            "magnification": "3x optical/macro zoom",
            "lighting": "Even diffuse white light (5000K)",
            "format": "JPEG 24-bit RGB",
            "resolution": "1280x960"
        },
        "samples": [
            {
                "filename": "sample_augmentin_genuine.jpg",
                "target_brand": "Augmentin 625mg",
                "batch_number": "B492",
                "gtin": "08964000123456",
                "printed_expiry": "2026-12-31",
                "packaging_type": "Authentic Offset Lithography Carton",
                "expected_verdict": "GENUINE",
                "expected_score_range": [85, 100],
                "purpose": "Control baseline showing sharp typography edges and absence of halftone noise."
            },
            {
                "filename": "sample_panadol_expiry_mismatch.jpg",
                "target_brand": "Panadol Extra",
                "batch_number": "P811",
                "gtin": "08964000654321",
                "printed_expiry": "2027-12-31",
                "packaging_type": "Tampered Genuine Box (Date Modified)",
                "expected_verdict": "SUSPECTED_COUNTERFEIT",
                "expected_score_range": [0, 20],
                "purpose": "Validates Layer 1 database hard-gate rejection when printed date deviates from registered official date."
            },
            {
                "filename": "sample_brufen_fake_halftone.jpg",
                "target_brand": "Brufen 400mg",
                "batch_number": "BR204",
                "gtin": "08964000987654",
                "printed_expiry": "2026-08-31",
                "packaging_type": "Commercial Inkjet Reprint on Cardstock",
                "expected_verdict": "REVIEW RECOMMENDED",
                "expected_score_range": [50, 75],
                "purpose": "Validates Layer 2 visual detection of CMYK halftone dot patterns and fuzzy line borders."
            },
            {
                "filename": "sample_arinac_unregistered.jpg",
                "target_brand": "Arinac Forte",
                "batch_number": "AR999",
                "gtin": "08964000112233",
                "printed_expiry": "2025-11-30",
                "packaging_type": "Illicit Packaging / Fabricated Batch",
                "expected_verdict": "SUSPECTED_COUNTERFEIT",
                "expected_score_range": [0, 0],
                "purpose": "Confirms zero-score hard stop when batch code is absent from the official registry."
            }
        ]
    }

def package_dataset_to_zip():
    """Generates all samples, writes manifest, and packs demo_dataset.zip."""
    print("=" * 70)
    print("DAWAE-CHECK: GENERATING PHYSICAL TEST DATASET & ATTACHMENT 3")
    print("=" * 70)
    
    # 1. Ensure output directory exists
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    
    # 2. Render and save all 4 sample images
    tasks = [
        ("sample_augmentin_genuine.jpg", generate_sample_augmentin_genuine),
        ("sample_panadol_expiry_mismatch.jpg", generate_sample_panadol_expiry_mismatch),
        ("sample_brufen_fake_halftone.jpg", generate_sample_brufen_fake_halftone),
        ("sample_arinac_unregistered.jpg", generate_sample_arinac_unregistered),
    ]
    
    for filename, generator_func in tasks:
        output_file = DATASET_DIR / filename
        print(f" -> Rendering 3x macro visual: {filename}...")
        img = generator_func()
        img.save(output_file, "JPEG", quality=95)
        print(f"    Saved: {output_file} ({IMAGE_WIDTH}x{IMAGE_HEIGHT})")
        
    # 3. Write manifest.json
    manifest_path = DATASET_DIR / "manifest.json"
    manifest_data = build_dataset_manifest()
    print(" -> Writing dataset index: manifest.json...")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"    Saved: {manifest_path}")

    # 4. Create demo_dataset.zip
    print(f" -> Compressing into archive: {ZIP_OUTPUT_PATH}...")
    with zipfile.ZipFile(ZIP_OUTPUT_PATH, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in DATASET_DIR.iterdir():
            if file_path.is_file():
                arcname = f"dataset/{file_path.name}"
                zipf.write(file_path, arcname=arcname)
                print(f"    Archived: {arcname}")
                
    zip_size_kb = ZIP_OUTPUT_PATH.stat().st_size / 1024
    print("=" * 70)
    print(f"SUCCESS: demo_dataset.zip created successfully ({zip_size_kb:.1f} KB)")
    print(f"Location: {ZIP_OUTPUT_PATH}")
    print("=" * 70)

if __name__ == "__main__":
    package_dataset_to_zip()