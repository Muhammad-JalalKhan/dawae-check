
<div align="center">

# 🛡️ Dawae-Check (دواء چیک)
### AI-Powered Point-of-Care Pharmaceutical Verification Pipeline

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Expo](https://img.shields.io/badge/Frontend-Expo%20%2F%20React%20Native-000020.svg?style=flat&logo=expo)](https://expo.dev/)
[![AI Vision Engine](https://img.shields.io/badgeqwen-vl-plus-6366F1.svg)](https://dashscope.aliyun.com/)
[![Database](https://img.shields.io/badge/Database-Supabase%20PostgreSQL-3ECF8E.svg?style=flat&logo=supabase)](https://supabase.com/)
[![Deployment](https://img.shields.io/badge/Cloud-Render-46E3B7.svg?style=flat&logo=render)](https://render.com/)

**Instant point-of-care medicine verification powered by sub-pixel packaging print forensics and deterministic regulatory serialization.**

[Live API Docs](https://dawae-check-api.onrender.com/docs) • [Architecture Specs](ARCHITECTURE.md) • [Database Schema](DATABASE_SCHEMA.md) • [Scoring Logic](SCORING_LOGIC.md)

</div>

---

## 📌 Verification Pipeline Overview

<p align="center">
  <img src="pipeline_architecture.png" alt="Hybrid AI Pharmaceutical Verification Pipeline" width="100%" />
</p>

The Dawae-Check pipeline operates in 4 synchronized phases to eliminate both digital serialization clones and physical packaging counterfeits:

1. **Scanning:** High-resolution capture via a 3x macro camera reticle optimized for medicine carton flaps.
2. **OCR Extraction:** Multimodal extraction of packaging metadata (Batch Number, Expiry Date, GTIN/Barcode, and DRAP registration codes).
3. **Verification Engine:**
   * **Layer 1 (Database Server):** Real-time deterministic check against the official DRAP registry with automated flap-inferred registration mapping.
   * **Layer 2 (Microscopic Vision & Neural Network):** Sub-pixel print physics analysis checking for CMYK inkjet halftone dithering, typography edge bleed, and restamped dates.
4. **Final Output:** Instant binary authenticity verdict (**GENUINE** or **COUNTERFEIT ALERT**) with projected 2D defect bounding boxes.

---

## ⚠️ The Problem: Why Digital Barcodes Fail

Standard barcodes and 2D DataMatrix codes only store alphanumeric text strings. Counterfeiting syndicates exploit this fundamental vulnerability by:
* **Duplicating Authentic Codes:** Photocopying legitimate 2D DataMatrix barcodes from genuine medicine cartons onto illicit boxes.
* **Date Restamping:** Chemical scrubbing and thermal overprinting of expired lot numbers.
* **Secondary Packaging Gaps:** Medicine carton flaps frequently omit the explicit DRAP registration number, leaving point-of-care dispensers unable to verify authenticity on standard lookup portals.

Dawae-Check bridges this gap by validating both the **digital registry** and the **physical printing process** of the carton simultaneously.

---

## ⚙️ Core Architecture & Dual-Gate Engine


<img width="2816" height="1536" alt="Gemini_Generated_Image_hh6blrhh6blrhh6b" src="https://github.com/user-attachments/assets/6d5d993d-5839-41c2-be63-fda7ed9f0f4b" />

                      
                      ┌────────────────────────┐
                      │ Scanned Flap Photo     │
                      └───────────┬────────────┘
                                  │
             ┌────────────────────┴────────────────────┐
             ▼                                         ▼
┌───────────────────────────┐             ┌───────────────────────────┐
│ Layer 1: Regulatory Match │             │ Layer 2: Forensic AI      │
│ - Batch & GTIN resolution │             │ - Qwen2.5-VL micro-print  │
│ - Official expiry check   │             │ - Halftone dot inspection │
│ - Inferred DRAP mapping   │             │ - Typography edge bleed   │
│ - Multi-node clone check  │             │ - 2D Defect Bounding Boxes│
└─────────────┬─────────────┘             └─────────────┬─────────────┘
│ (S_db, S_rule)                          │ (S_visual)
└────────────────────┬────────────────────┘
▼
┌───────────────────────────────┐
│    Multiplicative Scoring     │
│  S_final = S_db × (0.60×S_r   │
│           + 0.40×S_v)         │
└───────────────┬───────────────┘
▼
┌───────────────────────────────┐
│ Verdict: GENUINE / SUSPECTED  │
└───────────────────────────────┘


### Mathematical Multiplicative Gate
Verification enforces a strict zero-tolerance hard gate:

$$S_{\text{final}} = S_{\text{db}} \times \left(0.60 \times S_{\text{rule}} + 0.40 \times S_{\text{visual}}\right)$$

* **$S_{\text{db}} \in \{0.0, 1.0\}$:** Hard gate binary multiplier. Evaluates to `0.0` immediately if the batch is unregistered, expired, or flagged as a cloned serial across distant locations.
* **$S_{\text{rule}} \in [0, 100]$:** Serialization rule score (GTIN format, expiration consistency, and manufacturer alignment).
* **$S_{\text{visual}} \in [0, 100]$:** Micro-texture print forensic score evaluated by Qwen2.5-VL.

### Automated Flap-Inferred DRAP Logic
When a medicine carton flap only shows batch numbers and dates without an explicit DRAP number:
1. The engine queries `batch_registry` using the scanned `(GTIN, batch_number)` composite pair.
2. If found, it automatically infers and validates `record.drap_reg_number`, setting status to `INFERRED_FROM_REGISTRY`.
3. If an explicit DRAP registration is visible on the package, it confirms an exact match (`VERIFIED_MATCH`) or triggers an alert on contradiction.

---

## 💊 Seeded Pharmaceutical Registry

Dawae-Check is pre-seeded with 15 verified pharmaceutical packages photographed directly from retail and dispensary stock:

| Brand Name & Strength | Manufacturer | Batch No | GTIN-14 | DRAP Reg / Enl | Official Expiry |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Lowplat Plus 75mg** | PharmEvo (Pvt.) Ltd. | `6D284` | `08964001422372` | `047177` | 2028-03-31 |
| **Rosut-10 10mg** | Genix Pharma | `051` | `08964001581987` | `056081` | 2027-07-31 |
| **Valtic 40mg** | Tabros Pharma (Pvt) Ltd. | `205` | `08964002023370` | `055899` | 2027-04-30 |
| **Valtic 40mg** | Tabros Pharma (Pvt) Ltd. | `217` | `08964002023370` | `055899` | 2027-09-30 |
| **Nuberol Forte** | The Searle Company Ltd. | `DH0273` | `08964000271960` | `027196` | 2029-05-31 |
| **B-Card 5mg** | The Searle Company Ltd. | `KSH002` | `08964001790990` | `104015` | 2028-04-19 |
| **Nupenta 40mg** | Standpharm Pakistan | `T37031` | `08964002066025` | `095820` | 2027-10-31 |
| **Concor 2.5mg** | Martin Dow Marker Ltd | `47235` | `08964001517108` | `028000` | 2029-04-06 |
| **Concor 5mg** | Martin Dow Marker Ltd | `46955` | `08964001517115` | `010194` | 2029-03-08 |
| **Ciprofloxacin 500mg** | Stanley Pharmaceuticals | `A-173` | `08964001786122` | `032008` | 2029-01-31 |
| **Pasmec Tablets** | Pasteur & Fleming Pharma | `414` | *Flap Scan* | `01188` | 2027-05-31 |
| **Mektum Homoeo Drops**| Mektum Homoeo Pharma | `50497` | *Flap Scan* | `00126` | 2028-04-30 |
| **Gas-Gone Syrup** | Swift Care Pharma (Pvt) Ltd. | `014` | *Flap Scan* | `00723` | 2029-03-31 |
| **Calcimix Syrup** | Swift Care Pharma (Pvt) Ltd. | `007` | *Flap Scan* | `00723` | 2028-11-30 |
| **Pediatric Allergy Syrup** | Licensed Pharma | `07A26` | *Flap Scan* | `009763` | 2029-01-31 |

---

## 📂 Repository Structure

```text
Dawae-check/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/  # Verification routes (/verify-packaging)
│   │   ├── core/              # Config, CORS settings, database sessions
│   │   ├── models/            # SQLAlchemy models (batch_registry, scanned_logs)
│   │   ├── schemas/           # Pydantic validation schemas
│   │   └── services/          # Gate 1 (db_gate.py) & Gate 2 (ai_engine.py)
│   ├── seed.py                # Idempotent database seeder (15 real medicines)
│   ├── Dockerfile             # Production container definition
│   └── requirements.txt       # Python dependencies
│
├── mobile_expo/               # Cross-platform client (Android, iOS & Web)
│   ├── App.tsx                # Scanner viewfinder, HUD & Defect canvas
│   ├── package.json           # React Native / Expo SDK 54 dependencies
│   └── app.json               # Application configuration
│
├── dataset/                   # High-resolution packaging macro test suite
├── indigenous medicine data/  # Regional Pakistani pharmaceutical packaging data
├── demo_dataset.zip           # Packaged benchmark test images
├── docker-compose.yml         # Local container orchestration
├── render.yaml                # Infrastructure-as-code for Render cloud deploy
└── pipeline_architecture.png  # Pipeline architecture infographic

🚀 Quickstart Guide
1. Backend API Deployment (FastAPI)
PowerShell
cd B:\dawaeCheck\Dawae-check\backend

# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables (.env)
# DATABASE_URL=postgresql+asyncpg://postgres:...@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
# DASHSCOPE_API_KEY=sk-...
# DASHSCOPE_BASE_URL=[https://ws-b973pux4uxag20i2.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1](https://ws-b973pux4uxag20i2.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1)
# AI_MODEL_NAME=qwen-vl-plus

# 4. Run idempotent database seeding
python seed.py

# 5. Start API locally
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
Interactive Swagger UI will be available at: http://localhost:8000/docs.

2. Frontend Setup (Expo SDK 54)
PowerShell
cd B:\dawaeCheck\Dawae-check\mobile_expo

# 1. Install dependencies
npm install

# 2. Launch Metro Bundler
npx expo start -c
Physical Device (Android/iOS): Open the Expo Go app and scan the terminal QR code.

Web Browser Preview: Press w to launch the client on http://localhost:8081.

🔒 Security & Verification Integrity
Zero Hardcoded Secrets: Strict .gitignore rules prevent credential leaks. All database passwords and cloud API keys are read via environment variables.

Audit Trail Persistence: Every verification query is logged asynchronously with timestamped device hashes, extracted tokens, and bounding box coordinates in scanned_logs to detect multi-facility serial cloning.



---

### Step 3: Push Everything to GitHub

Run these commands in PowerShell:

```powershell
cd B:\dawaeCheck\Dawae-check

# 1. Stage README and the architecture image
git add README.md pipeline_architecture.png

# 2. Commit
git commit -m "docs: add comprehensive README with hybrid verification pipeline diagram"

# 3. Push to your live repository
git push origin main
