# Dawae-Check — Technical Specification (spec.md)

**AI Micro-Texture & Hybrid Pharmaceutical Verification Platform**
Hackathon: AI Hackathon Pakistan 2026 — Healthcare Track (Alkhidmat Foundation / Bano Qabil / Alibaba Cloud)
Sprint Window: Aug 23 – Aug 27, 2026 (4 build days + finale prep)
IDE: Qoder IDE (Quest Mode) with MCP PostgreSQL integration

---

## 1. Project Summary

Dawae-Check stops counterfeit medicine at the point of care. Instead of trusting a scannable QR/DataMatrix code (which counterfeiters simply photocopy), the system runs a **Dual-Gate Verification**:

1. **Layer 1 — Database Gate (deterministic):** OCR-extracted GTIN, batch number, DRAP registration number, and expiry date are cross-checked against an official batch registry.
2. **Layer 2 — Visual Micro-Texture Gate (AI):** A 3x macro photo of the packaging is analyzed by Qwen2.5-VL for print artifacts (halftone dots, ink bleed, barcode grade) that separate industrial offset printing from cheap counterfeit printing.

Both scores combine into one composite authenticity verdict. If the database gate fails, the verdict is forced to COUNTERFEIT regardless of print quality — a tampered expiry date is disqualifying on its own.

**Users:** field healthcare workers, dispensaries, pharmacists, patients.
**Core deliverables for this sprint:** FastAPI backend, PostgreSQL/Supabase schema, Qwen2.5-VL AI pipeline, Flutter mobile app, Dockerized deployment.

---

## 2. Composite Scoring Formula

```
S_final = w1 * S_DB + w2 * S_visual

S_DB     ∈ {0, 100}   — binary: 100 if batch exists AND expiry matches AND serial is not cloned; else 0
S_visual ∈ [0, 100]   — Qwen2.5-VL print-quality confidence

w1 = 0.60   w2 = 0.40

Hard rule: IF S_DB == 0 THEN S_final = 0 (forced), regardless of S_visual
```

Verdict bands (apply only when S_DB = 100, since S_DB = 0 forces S_final = 0):

| S_final       | Verdict               |
|---------------|------------------------|
| 80 – 100      | GENUINE                |
| 50 – 79       | REVIEW_RECOMMENDED     |
| 0 – 49        | SUSPECTED_COUNTERFEIT  |

---

## 3. Technology Stack

| Layer | Technology |
|---|---|
| AI / Vision | Alibaba Cloud Model Studio — `qwen2.5-vl-72b-instruct` (fallback `qwen2.5-vl-7b-instruct`) via `dashscope` SDK or OpenAI-compatible client |
| Backend | FastAPI (Python 3.11+), Pydantic v2, SQLAlchemy 2.0 ORM, Alembic for migrations |
| Database | PostgreSQL 15+ (Supabase-hosted) |
| Mobile | Flutter 3.x, `camera` package (3x macro zoom lock), `dio`/`http` for multipart uploads, `CustomPainter` for bbox overlays |
| Image Processing | OpenCV (preprocessing: crop, sharpen, normalize before sending to Qwen) |
| Deployment | Docker + Docker Compose, hosted on Alibaba Cloud ECS / Railway / Render |
| Dev Tooling | Qoder IDE (Quest Mode scaffolding), MCP server for direct Postgres access |

---

## 4. Database Schema (PostgreSQL DDL)

```sql
-- =========================================================
-- 1. manufacturers
-- =========================================================
CREATE TABLE manufacturers (
    manufacturer_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name        VARCHAR(255) NOT NULL,
    drap_license_number VARCHAR(100) UNIQUE NOT NULL,
    contact_email       VARCHAR(255),
    contact_phone       VARCHAR(50),
    address             TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- 2. batch_registry
-- =========================================================
CREATE TABLE batch_registry (
    batch_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_id     UUID NOT NULL REFERENCES manufacturers(manufacturer_id),
    gtin                VARCHAR(20) NOT NULL,
    brand_name          VARCHAR(255) NOT NULL,
    batch_number        VARCHAR(100) NOT NULL,
    drap_reg_number     VARCHAR(100) NOT NULL,
    official_expiry     DATE NOT NULL,
    manufacture_date    DATE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_gtin_batch UNIQUE (gtin, batch_number)
);

CREATE INDEX idx_batch_registry_gtin_batch ON batch_registry (gtin, batch_number);
CREATE INDEX idx_batch_registry_drap ON batch_registry (drap_reg_number);

-- =========================================================
-- 3. scanned_logs
-- =========================================================
CREATE TABLE scanned_logs (
    scan_id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id              VARCHAR(100) UNIQUE NOT NULL,
    device_id               VARCHAR(100) NOT NULL,
    facility_id              VARCHAR(100) NOT NULL,
    matched_batch_id         UUID REFERENCES batch_registry(batch_id),
    extracted_gtin           VARCHAR(20),
    extracted_batch_number   VARCHAR(100),
    extracted_expiry         DATE,
    extracted_drap_reg       VARCHAR(100),
    layer1_status            VARCHAR(20) NOT NULL,   -- PASSED | FAILED
    layer1_reasons           JSONB,
    layer2_status             VARCHAR(20) NOT NULL,   -- PASSED | FAILED
    layer2_print_score        NUMERIC(5,2),
    layer2_defects            JSONB,                  -- array of {label, confidence, bbox_2d}
    authenticity_score        NUMERIC(5,2) NOT NULL,
    verdict                   VARCHAR(30) NOT NULL,   -- GENUINE | REVIEW_RECOMMENDED | SUSPECTED_COUNTERFEIT
    latitude                  DOUBLE PRECISION,
    longitude                 DOUBLE PRECISION,
    image_url                 TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_scanned_logs_gtin_batch ON scanned_logs (extracted_gtin, extracted_batch_number);
CREATE INDEX idx_scanned_logs_device ON scanned_logs (device_id);
CREATE INDEX idx_scanned_logs_created_at ON scanned_logs (created_at);

-- Used for cloned-serial detection: count scans of the same gtin+batch
-- across distinct facility_id/geolocation within a rolling time window.
```

---

## 5. API Contract

### `POST /api/v1/verify-packaging`

**Request (multipart/form-data):**

| Field | Type | Notes |
|---|---|---|
| `file` | binary (JPEG) | 3x macro packaging photo |
| `device_id` | string | e.g. `MOB-98421` |
| `facility_id` | string | e.g. `ALK-DISP-KHI-04` |
| `latitude` | float, optional | for cloned-serial geo-check |
| `longitude` | float, optional | for cloned-serial geo-check |

**Response (application/json):**

```json
{
  "request_id": "req-88321-khi",
  "verdict": "SUSPECTED_COUNTERFEIT",
  "authenticity_score": 18,
  "layer1_database_check": {
    "status": "FAILED",
    "reasons": [
      "Expiry Date Mismatch: Box prints '12/2027', DB record states '12/2023' for Batch B492"
    ],
    "matched_record": {
      "gtin": "08964000123456",
      "brand_name": "Augmentin 625mg",
      "batch_number": "B492",
      "official_expiry": "2023-12-31"
    }
  },
  "layer2_visual_check": {
    "status": "FAILED",
    "print_quality_score": 35,
    "detected_defects": [
      { "label": "Digital Halftone Ink Dots Detected", "confidence": 0.94, "bbox_2d": [142, 210, 310, 420] },
      { "label": "Fine-Print Edge Blur", "confidence": 0.89, "bbox_2d": [512, 110, 580, 390] }
    ]
  },
  "technical_summary": "High risk of counterfeiting. Printed expiry date deviates from official DRAP batch registration, and digital halftone artifacts indicate commercial inkjet re-printing."
}
```

### Supporting endpoints (build if time permits, Day 3–4)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/batches` | POST | Admin: register a new batch (manufacturer seed data) |
| `/api/v1/batches/{gtin}/{batch_number}` | GET | Lookup a batch record |
| `/api/v1/scans/{facility_id}` | GET | Audit trail for a facility (dashboard) |
| `/api/v1/health` | GET | Liveness check for deployment |

---

## 6. AI Pipeline (`ai_engine.py`)

**Flow per request:**
1. Receive image → OpenCV preprocessing (auto-crop to macro region, contrast normalize, resize to model-friendly resolution).
2. Call Qwen2.5-VL twice (or one combined call) with a strict system prompt:
   - **OCR extraction pass:** returns `gtin`, `batch_number`, `expiry_date`, `drap_reg_number` as structured JSON.
   - **Visual defect pass:** returns `print_quality_score` (0–100) and `detected_defects[]` with `label`, `confidence`, `bbox_2d`.
3. Enforce **JSON-only output** in the system prompt (no prose, no markdown fences) and validate with Pydantic; retry once on parse failure.
4. Pass OCR fields to the DB verification service (`db_gate.py`) for Layer 1.
5. Combine `S_DB` and `S_visual` using the composite formula in Section 2.
6. Persist the full result to `scanned_logs` and return the response contract from Section 5.

**System prompt requirements (both passes):**
- Output must be valid JSON only, matching a fixed schema — nothing else.
- `bbox_2d` coordinates in `[x_min, y_min, x_max, y_max]` pixel format relative to the submitted image.
- Explicitly instruct the model to look for: halftone/dithering dot clusters, typography edge blur/ink bleed, barcode/DataMatrix contrast and quiet-zone quality (ISO 15415), color/layout misalignment, foil/hologram irregularities.

**Layer 1 Database Gate logic (`db_gate.py`):**
- Lookup `(gtin, batch_number)` in `batch_registry`.
- If no match → `FAILED`, reason: "Unregistered batch".
- If match but `extracted_expiry != official_expiry` → `FAILED`, reason: expiry mismatch (include both values).
- Cloned-serial check: count `scanned_logs` rows for same `(gtin, batch_number)` within a rolling window (e.g., 24h) across distinct `facility_id`/geolocation beyond a configurable threshold → `FAILED`, reason: "Serial scanned N times across distinct locations".
- All checks pass → `PASSED`, `S_DB = 100`; else `S_DB = 0`.

---

## 7. Mobile App (Flutter)

**Screens:** Camera → Loading → Result.

- **Camera screen:** lock zoom at 3x, focal lock, bounding-box guide overlay to standardize macro framing, capture button disabled until focus confirmed.
- **Loading screen:** shows upload/analysis progress while awaiting API response.
- **Result screen:** verdict banner (GENUINE / REVIEW_RECOMMENDED / SUSPECTED_COUNTERFEIT), authenticity score, `CustomPainter` overlay drawing colored bounding boxes over `detected_defects[].bbox_2d` on the captured image, expandable technical summary and reasons list.
- **Networking:** multipart POST via `dio` to `/api/v1/verify-packaging`, include `device_id`, `facility_id`, and device geolocation (with permission).

---

## 8. Project Folder Structure (for Qoder Quest Mode scaffolding)

```
dawae-check/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/verify.py
│   │   ├── api/v1/batches.py
│   │   ├── services/ai_engine.py
│   │   ├── services/db_gate.py
│   │   ├── services/scoring.py
│   │   ├── models/ (SQLAlchemy models: manufacturer, batch_registry, scanned_log)
│   │   ├── schemas/ (Pydantic request/response schemas)
│   │   ├── core/config.py
│   │   └── db/session.py
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── mobile/
│   └── lib/
│       ├── screens/camera_screen.dart
│       ├── screens/loading_screen.dart
│       ├── screens/result_screen.dart
│       ├── widgets/bbox_painter.dart
│       └── services/api_client.dart
├── docker-compose.yml
└── .env.example
```

---

## 9. Environment Variables (`.env.example`)

```
DASHSCOPE_API_KEY=
QWEN_MODEL=qwen2.5-vl-72b-instruct
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dawaecheck
SUPABASE_URL=
SUPABASE_KEY=
CLONE_DETECTION_WINDOW_HOURS=24
CLONE_DETECTION_LOCATION_THRESHOLD=3
```

---

## 10. Team Role Assignments

| Role | Owner | Deliverables |
|---|---|---|
| AI & Computer Vision Lead (Team Lead) | — | `ai_engine.py`, Qwen prompt engineering, OpenCV preprocessing, composite scoring |
| Mobile App Developer | — | Flutter camera/loading/result screens, API integration, bbox overlay |
| Cloud & Backend Engineer | — | FastAPI routes, DB migrations, service layer, Docker deployment |
| UI/UX Designer & Pitch Specialist | — | Figma prototypes, real vs. fake packaging dataset (3 vs 3), pitch deck, demo script |

---

## 11. 4-Day Sprint Plan

| Day | Focus |
|---|---|
| Aug 23 (Day 1) | Obtain Model Studio API keys; scaffold FastAPI in Qoder Quest Mode; init Flutter app with 3x macro camera; Figma wireframes |
| Aug 24 (Day 2) | Tune Qwen2.5-VL prompts for OCR + bbox_2d defect extraction; build DB tables with seed/mock data; collect real vs. fake packaging samples |
| Aug 25 (Day 3) | Connect Flutter app to FastAPI backend end-to-end; wire AI output into DB verification; draft pitch deck |
| Aug 26 (Day 4) | Build Android release APK; deploy FastAPI to cloud host; rehearse presentation; record backup demo video |
| Aug 27 (Finale) | Final dry runs, live stage presentation |

---

## 12. Definition of Done (Hackathon MVP)

- [ ] `/api/v1/verify-packaging` returns the exact JSON contract in Section 5 for both genuine and counterfeit test samples.
- [ ] Database gate correctly flags at least: unregistered batch, expiry mismatch, cloned serial.
- [ ] Visual gate returns at least 2 defect categories with bounding boxes on a known fake sample.
- [ ] Flutter app captures a 3x macro image, uploads it, and renders the verdict with overlaid defect boxes.
- [ ] Backend deployed and reachable via public URL; `/api/v1/health` returns 200.
- [ ] 3 genuine + 3 counterfeit real packaging samples tested end-to-end with correct verdicts.
