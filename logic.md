# Dawae-Check — Logic & Architecture Notes

## Libraries & Choices

| Library | Why |
|---------|-----|
| **FastAPI** | Async-native, automatic OpenAPI docs, Pydantic integration — ideal for a hackathon-speed project that still needs production-quality API contracts. |
| **SQLAlchemy 2.0 (async)** | Mature ORM with first-class `asyncio` support via `async_sessionmaker`. Declarative `mapped_column` style gives us type-safe models. |
| **asyncpg** | Fastest async PostgreSQL driver for Python. Chosen over `psycopg` (v3 async) because asyncpg is battle-tested, widely deployed, and has lower latency for bulk reads — important for scan-heavy workloads. |
| **aiosqlite** | Added to `requirements.txt` purely for local development / CI where Postgres may not be available. The app can be pointed at a SQLite URL (`sqlite+aiosqlite:///./dev.db`) for quick testing. |
| **Alembic** | Standard migration tool for SQLAlchemy. Configured with async support so migrations run against Postgres without blocking. |
| **pydantic-settings** | Loads env vars + `.env` file into a typed `Settings` dataclass. Cleaner than raw `os.getenv` calls and gives us validation for free. |
| **python-dotenv** | Required by pydantic-settings to read `.env` files. |
| **python-multipart** | Needed by FastAPI for `UploadFile` / form-data endpoints (scan image uploads in Task 3). |
| **uvicorn[standard]** | ASGI server with `websockets`, `httptools`, and `uvloop` for production-grade async serving. |

## Function Roles

### `main.py`
- `lifespan()` — async context manager that runs on app startup/shutdown. Creates all tables via `Base.metadata.create_all` (fallback safety net) and disposes the engine on exit.
- `root()` — health-check endpoint returning `{"status": "ok"}`.

### `core/config.py`
- `Settings` — pydantic-settings model that reads from `.env` / environment variables. Single source of truth for all config.
- `settings` — singleton instance used throughout the app.

### `db/session.py`
- `engine` — async SQLAlchemy engine created from `DATABASE_URL`.
- `async_session_factory` — `async_sessionmaker` that produces `AsyncSession` instances.
- `Base` — shared `DeclarativeBase` for all models.
- `get_session()` — FastAPI `Depends()` generator for request-scoped sessions.

### `models/manufacturer.py`
- `Manufacturer` — ORM model for `manufacturers` table. Has a `batches` relationship to `BatchRegistry`.

### `models/batch_registry.py`
- `BatchRegistry` — ORM model for `batch_registry` table. Includes `UniqueConstraint(gtin, batch_number)` and two indexes. Relationships to `Manufacturer` and `ScannedLog`.

### `models/scanned_log.py`
- `ScannedLog` — ORM model for `scanned_logs` table. JSONB columns for `layer1_reasons` and `layer2_defects`. Three indexes for query performance.

### `seed.py`
- Creates GSK Pakistan and Abbott Laboratories Pakistan as manufacturers.
- Inserts 3 batch_registry rows (Augmentin, Panadol Extra, Brufen).
- Arinac Forte is intentionally **not** inserted — it triggers "unregistered batch" when scanned.
- Idempotent: checks for existing rows before inserting.

## Migration Approach

We use a **dual strategy**:
1. **Alembic** is configured and ready for production migrations (`alembic/env.py` is async-aware).
2. **`Base.metadata.create_all`** runs in the FastAPI lifespan as a safety net, ensuring tables exist even if migrations haven't been applied (useful for hackathon demos and Docker first-runs).

For production, you'd generate migrations with `alembic revision --autogenerate` and apply with `alembic upgrade head`. The `create_all` call is idempotent — it does nothing if tables already exist.

## Assumptions

1. **UUID generation**: Using PostgreSQL's `gen_random_uuid()` (available in PG 13+) rather than application-side UUID generation. This keeps IDs consistent even with direct DB inserts.
2. **SQLite compatibility**: The `gen_random_uuid()` server_default won't work on SQLite. For local SQLite testing, we rely on `create_all` (which ignores server defaults in SQLite) and the seed script assigns UUIDs via SQLAlchemy defaults.
3. **JSONB columns**: `layer1_reasons` and `layer2_defects` use PostgreSQL JSONB. If SQLite is used, these fall back to plain TEXT storage.
4. **No API routers wired yet**: Task 3 will add the `verify` and `batches` routers. The app currently only has the health-check route.
5. **Arinac Forte**: No batch_registry row is created — this is by design to test the "batch not found" path in Layer-1 verification.

---

## Task 2 — Scoring & Gate Logic

### `services/db_gate.py` — `check_database_gate()`

**Role:** Pure Layer-1 database gate. Looks up (GTIN, batch_number) in `batch_registry` and verifies expiry.

**Parameters:**
- `session` — AsyncSession
- `extracted_gtin`, `extracted_batch_number`, `extracted_expiry` — OCR-extracted values
- `facility_id` — scanning facility identifier
- `latitude`, `longitude` — optional GPS coords (reserved for future use)

**Returns:** `dict` with keys:
- `status` — "PASSED" | "FAILED"
- `reasons` — list of failure reason strings
- `matched_batch_id` — UUID or None
- `s_db` — 1 if batch exists, 0 otherwise
- `s_rule` — 100 if clean match, 50 if clone detected, 0 if mismatch or not found
- `matched_record` — dict with gtin, brand_name, batch_number, official_expiry (or None)

**Logic (5 states):**
1. No match → FAILED, s_db=0, s_rule=0, reason="Unregistered batch"
2. Match but expiry mismatch → FAILED, s_db=1, s_rule=0, reason="Expiry mismatch: extracted X vs official Y"
3. Match, expiry matches, clone detected → FAILED, s_db=1, s_rule=50, reason="Serial scanned across multiple distinct facilities (clone detected...)"
4. Match, expiry matches, no clone → PASSED, s_db=1, s_rule=100

Clone detection is wired directly into db_gate via `check_serial_clone()` from `clone_detection.py`. After batch existence and expiry are confirmed, db_gate queries `scanned_logs` for distinct `facility_id` values within the configured time window. If the count meets or exceeds `CLONE_DETECTION_LOCATION_THRESHOLD` (default 3), the serial is flagged as cloned.

**This function is intentionally simple and isolated** so the gate logic can be swapped or extended later.

---

### `services/scoring.py` — `compute_final_score()`

**Role:** Combines Layer-1 (DB gate) and Layer-2 (AI visual) into a final authenticity score and verdict.

**Parameters:**
- `s_db` (int) — 0 or 1, database gate flag
- `s_rule` (int) — 0 or 100, deterministic rule score
- `s_visual` (float) — 0–100, AI/visual inspection score

**Returns:** `tuple[float, str]` — (authenticity_score, verdict)

**Authoritative formula (overrides spec.md Section 2):**
```
S_final = S_DB × (0.60 × S_rule + 0.40 × S_visual)
```

**Verdict bands:**
- 80–100 → GENUINE
- 50–79 → REVIEW_RECOMMENDED
- 0–49 → SUSPECTED_COUNTERFEIT

**Key property:** When s_db=0, score is always 0 (hard gate). When s_rule=0 (expiry mismatch), max possible score is 40 → always SUSPECTED_COUNTERFEIT regardless of s_visual.

---

### `test_scoring_local.py`

Standalone script that seeds the DB and runs 5 test scenarios through db_gate + scoring:

| # | Medicine | Scenario | s_db | s_rule | s_visual | Score | Verdict |
|---|----------|----------|------|--------|----------|-------|---------|
| 1 | Augmentin 625mg | Valid match | 1 | 100 | 85 | 94.0 | GENUINE |
| 2 | Panadol Extra | Expiry mismatch (extracted 2026-03-31 vs official 2025-03-31) | 1 | 0 | 35 | 14.0 | SUSPECTED_COUNTERFEIT |
| 3 | Arinac Forte | Unregistered batch | 0 | 0 | 35 | 0.0 | SUSPECTED_COUNTERFEIT |
| 4 | Brufen 400mg | Valid DB / fake print | 1 | 100 | 30 | 72.0 | REVIEW_RECOMMENDED |
| 5 | Augmentin CLONE | Cloned serial (3 distinct facilities) | 1 | 50 | 85 | 64.0 | REVIEW_RECOMMENDED |

**Brufen mock correction:** s_visual lowered from 90 → 30 to simulate detected print defects (halftone dots, ink bleed). Brufen is the "valid DB / fake print" case — the batch is real in the database but the physical packaging shows signs of counterfeiting. This ensures it lands in REVIEW_RECOMMENDED (score 72) rather than GENUINE.

**All three S_rule branches exercised:**
- S_rule=100 → Augmentin (clean match), Brufen (valid DB but fake print)
- S_rule=50 → Augmentin CLONE (clone detected across 3 distinct facilities)
- S_rule=0 → Panadol (expiry mismatch), Arinac (unregistered batch)

---

### S_rule Branches

Three s_rule values are implemented and exercised in tests:
- **S_rule=100**: Batch exists, expiry matches, no clone detected (clean match)
- **S_rule=50**: Batch exists, expiry matches, but clone detected (serial scanned across ≥3 distinct facilities within the time window)
- **S_rule=0**: Batch not found or expiry mismatch

### Formula vs spec.md Section 2

The authoritative formula `S_DB × (0.60 × S_rule + 0.40 × S_visual)` differs from spec.md Section 2 which used an additive approach with a +50 baseline for expiry mismatches. The multiplicative s_db acts as a **hard gate** — if the batch doesn't exist in the database, the score is always 0 regardless of visual quality. This prevents false positives where a visually convincing counterfeit could pass the DB check.

### Assumptions

1. **s_rule=50 is reachable**: Clone detection is wired into db_gate. The test script seeds 3 scanned_logs with distinct facility_ids to prove the branch works.
2. **s_visual is external**: This module does not produce s_visual — it comes from the AI engine (Task 3).
3. **SQLite compatibility**: The test script uses the existing SQLite dev.db fallback. Works identically to Postgres for these queries.
4. **Expiry comparison**: Exact date match required. Format normalised to Python `date` objects via `date.fromisoformat()`.

---

---

## Task 3 — API Endpoints & Deployment

### `schemas/__init__.py` — Pydantic Request/Response Models

**Role:** Typed validation for all API request bodies and response contracts.

**Key schemas:**
- `VerifyResponse` — full response contract for `/api/v1/verify-packaging` (matches spec.md Section 5)
- `Layer1DatabaseCheck` — Layer-1 result (status, reasons, matched_record)
- `Layer2VisualCheck` — Layer-2 result (status, print_quality_score, detected_defects)
- `DetectedDefect` — single visual defect with label, confidence, bbox_2d
- `BatchCreate` — request body for `POST /api/v1/batches`
- `BatchResponse` — batch record response with all fields
- `ScanLogResponse` — scan audit trail entry

---

### `services/ai_engine.py` — `analyze_packaging()`

**Role:** Accepts raw image bytes and returns OCR + visual defect analysis.

**Parameters:**
- `image_bytes` (bytes) — raw JPEG image from the upload

**Returns:** `dict` with two top-level keys:
- `ocr` — `{gtin, batch_number, expiry_date, drap_reg_number}`
- `visual` — `{print_quality_score (0-100), detected_defects: [{label, confidence, bbox_2d}]}`

**Mock AI Engine approach:**
When `MOCK_AI_ENGINE=true` (default for dev/local), returns a hardcoded Augmentin 625mg payload that matches the seed DB exactly (gtin=08964000123456, batch=B492, expiry=2026-12-31). This allows full end-to-end testing without an AI API key.

When `MOCK_AI_ENGINE=false`, raises `NotImplementedError` — the AI teammate will replace this with the real Qwen2.5-VL DashScope integration (OpenCV preprocessing + dual-pass prompting).

The mock returns the **same structure** as the real engine will, so the verify endpoint code never needs to change.

---

### `api/v1/verify.py` — `POST /api/v1/verify-packaging`

**Role:** Main verification endpoint. Accepts multipart image upload and returns the full dual-gate verdict.

**Request (multipart/form-data):**
- `file` — JPEG image (UploadFile)
- `device_id` — device identifier string
- `facility_id` — facility identifier string
- `latitude`, `longitude` — optional GPS coordinates

**Logic flow (8 steps):**
1. Generate unique `request_id` (format: `req-{uuid4_short}`)
2. Read image bytes and call `analyze_packaging()` from ai_engine
3. Extract OCR fields (gtin, batch_number, expiry_date, drap_reg_number)
4. Pass OCR fields to `check_database_gate()` from db_gate.py → Layer-1 result
5. Extract visual score from Layer-2 AI output
6. Call `compute_final_score(s_db, s_rule, s_visual)` from scoring.py
7. Persist full result to `scanned_logs` table
8. Return `VerifyResponse` matching spec.md Section 5 contract

**Response:** JSON with request_id, verdict, authenticity_score, layer1_database_check, layer2_visual_check, technical_summary.

**Helper:** `_build_technical_summary()` generates a human-readable summary based on verdict and layer results.

---

### `api/v1/batches.py` — Batch Management Endpoints

**`POST /api/v1/batches`** — Admin: register a new batch.
- Accepts: manufacturer_id, gtin, brand_name, batch_number, drap_reg_number, official_expiry, manufacture_date
- Checks for duplicate (gtin, batch_number) → 409 if exists
- Returns 201 with the created BatchResponse

**`GET /api/v1/batches/{gtin}/{batch_number}`** — Lookup a batch record.
- Returns BatchResponse or 404 if not found

---

### `api/v1/scans.py` — `GET /api/v1/scans/{facility_id}`

**Role:** Scan audit trail for a facility (dashboard use).
- Returns list of ScanLogResponse, most recent first, limited to 50 by default
- Query param: `limit` (int, default 50)

---

### `api/v1/health.py` — `GET /api/v1/health`

**Role:** Liveness probe for deployment health checks.
- Returns `{"status": "healthy", "version": "0.1.0"}`

---

### `main.py` — Router Wiring

All routers are included with prefix `/api/v1`:
- `health_router` → `GET /api/v1/health`
- `verify_router` → `POST /api/v1/verify-packaging`
- `batches_router` → `POST /api/v1/batches`, `GET /api/v1/batches/{gtin}/{batch_number}`
- `scans_router` → `GET /api/v1/scans/{facility_id}`

The lifespan function logs `MOCK_AI_ENGINE` status on startup.

---

### Docker Setup Decisions

**Dockerfile** (unchanged from Task 1 — already correct):
- Python 3.11-slim base image for small footprint
- pip install from requirements.txt, then COPY source
- Exposes port 8000, runs uvicorn

**docker-compose.yml:**
- `db` service: Postgres 15 with user `dawae` / password `dawae_pass` / database `dawaecheck`
- `backend` service: builds from `./backend`, maps port 8000, sets `DATABASE_URL` to connect to `db`, sets `MOCK_AI_ENGINE=true`
- Named volume `pgdata` for persistent database storage

---

### Deployment Approach

**Render (`render.yaml`):**
- Blueprint defines a Docker web service
- Points to `./backend/Dockerfile` with context `./backend`
- Environment variables: `DATABASE_URL` (manual sync), `MOCK_AI_ENGINE=true`, `DASHSCOPE_API_KEY` (manual sync)

**Railway/Render alternative (`backend/Procfile`):**
- `web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- Uses `$PORT` env var (set by platform) with 8000 fallback

**Deployment steps needed (with credentials):**
1. **Render:** Push to GitHub → connect repo → Render auto-detects `render.yaml` → set `DATABASE_URL` and `DASHSCOPE_API_KEY` in dashboard → deploy
2. **Railway:** `railway init` → `railway up` → set env vars in dashboard → `railway open` for public URL
3. **Docker Compose (VPS):** `docker-compose up -d --build` → backend available at `http://<server-ip>:8000`

---

### Verification Results

All endpoints tested successfully with SQLite + mock AI engine:

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/api/v1/health` | GET | 200 | Returns `{"status": "healthy", "version": "0.1.0"}` |
| `/api/v1/verify-packaging` | POST | 200 | Full response contract with layer1 + layer2 + verdict |
| `/api/v1/batches/{gtin}/{batch_number}` | GET | 200 | Returns Augmentin batch from seed data |
| `/api/v1/scans/{facility_id}` | GET | 200 | Returns audit trail list |
| `/api/v1/batches` | POST | 201 | Creates new batch (409 on duplicate) |
| `/` | GET | 200 | Root health check `{"status": "ok"}` |

---

*This file now serves as the complete backend map for Dawae-Check.*
