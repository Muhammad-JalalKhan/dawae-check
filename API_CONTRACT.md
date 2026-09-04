# API Contract Specification — Dawae-Check

This is the authoritative API contract for Dawae-Check. Both the backend (`backend/app/schemas/`) and the Flutter mobile client (`mobile_app/lib/services/`) must conform strictly to these exact keys, types, and nesting. Do not add, rename, or remove fields without explicit approval.

---

## 1. Core Verification Endpoint

### `POST /api/v1/verify-packaging`

Executes the dual-gate packaging verification pipeline: passes the macro photo to Qwen2.5-VL for OCR and defect detection, verifies data against Supabase `batch_registry`, calculates the authenticity score, and logs the scan.

#### Request (`multipart/form-data`)

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `file` | Binary (File) | **Yes** | 3x macro photo of packaging (JPEG/PNG, max 15MB) | `photo.jpg` |
| `device_id` | String | **Yes** | Unique client device identifier | `"MOB-98421"` |
| `facility_id` | String | **Yes** | Station or dispensary ID | `"ALK-DISP-KHI-04"` |
| `latitude` | Float | No | GPS latitude coordinate | `24.8607` |
| `longitude` | Float | No | GPS longitude coordinate | `67.0011` |

#### Success Response: `200 OK` (`application/json`)

```json
{
  "request_id": "req-88321-khi",
  "verdict": "GENUINE",
  "authenticity_score": 94,
  "layer1_database_check": {
    "status": "PASSED",
    "reasons": [
      "GTIN & Batch exist in DRAP registry",
      "Official expiry date matches packaging"
    ],
    "matched_record": {
      "gtin": "08964000123456",
      "brand_name": "Augmentin 625mg",
      "batch_number": "B492",
      "official_expiry": "2026-12-31"
    }
  },
  "layer2_visual_check": {
    "status": "PASSED",
    "print_quality_score": 85,
    "detected_defects": [
      {
        "label": "Digital Halftone Ink Dots Detected",
        "confidence": 0.94,
        "bbox_2d": [142, 210, 310, 420]
      }
    ]
  },
  "technical_summary": "Packaging verified genuine. Official batch registered with DRAP and offset lithography print quality confirmed."
}
Field Notes & Constraintsverdict (String): Strictly one of:"GENUINE" (Score 80–100)"REVIEW RECOMMENDED" (Score 50–79)"SUSPECTED_COUNTERFEIT" (Score 0–49)authenticity_score (Integer): Composite score $S_{\text{final}} \in [0, 100]$.matched_record (Object or null): Contains the official database record if found; returns null if the batch does not exist in batch_registry.bbox_2d (Array of Integers): Format is [ymin, xmin, ymax, xmax] normalized to a 0–1000 integer coordinate scale.Flutter Screen Mapping Formula:$$\text{left} = \left(\frac{\text{xmin}}{1000.0}\right) \times \text{imageDisplayWidth}$$$$\text{top} = \left(\frac{\text{ymin}}{1000.0}\right) \times \text{imageDisplayHeight}$$$$\text{right} = \left(\frac{\text{xmax}}{1000.0}\right) \times \text{imageDisplayWidth}$$$$\text{bottom} = \left(\frac{\text{ymax}}{1000.0}\right) \times \text{imageDisplayHeight}$$Error ResponsesHTTP StatusReasonPayload Format400 Bad RequestMissing required fields or invalid file format{"detail": "File upload missing or invalid format"}422 Unprocessable EntityModel unable to parse image or corrupt file{"detail": "Packaging unreadable or invalid image bytes"}500 Internal Server ErrorDatabase connection failure or Model Studio API timeout{"detail": "Internal verification pipeline error"}2. Supporting Management EndpointsHealth CheckGET /api/v1/healthResponse: 200 OKJSON{ "status": "ok" }
Direct Batch LookupGET /api/v1/batches/{gtin}/{batch_number}Response: 200 OKJSON{
  "gtin": "08964000123456",
  "brand_name": "Augmentin 625mg",
  "batch_number": "B492",
  "drap_reg_number": "REG-PAK-00201",
  "official_expiry": "2026-12-31",
  "is_active": true
}
Errors: 404 Not Found if the batch is unregistered.Facility Audit TrailGET /api/v1/scans/{facility_id}Response: 200 OKJSON[
  {
    "id": "uuid-here",
    "device_id": "MOB-98421",
    "facility_id": "ALK-DISP-KHI-04",
    "scanned_gtin": "08964000123456",
    "scanned_batch_number": "B492",
    "verdict": "GENUINE",
    "authenticity_score": 94,
    "created_at": "2026-08-23T10:15:30Z"
  }
]