# Build Phases — Dawae-Check

Phase-based execution tracker. Each phase has a strict exit condition. Do not move to the next phase until the current exit condition is verified.

---

## Phase 0 — Environment & Dependency Setup
**Goal:** Run the existing backend locally without dependency or configuration errors.
- [ ] Open workspace root directly at `Dawae-check/`
- [ ] Create virtual environment and install backend dependencies: `pip install -r backend/requirements.txt`
- [ ] Install missing AI dependencies: `pip install openai pillow`
- [ ] Configure `backend/.env` with `DATABASE_URL` (Supabase pooler) and `DASHSCOPE_API_KEY` (Alibaba Model Studio)
- [ ] Confirm `.env` is ignored in `.gitignore`
- [ ] Verify Flutter SDK: `flutter doctor`

**Exit condition:** Backend starts clean via `uvicorn backend.app.main:app --reload` and outputs database connection verified.

---

## Phase 1 — Real AI Integration & Backend Verification
**Goal:** Swap mock AI with live Qwen2.5-VL inference and prove the full dual-gate verification pipeline works.
- [ ] Populate database records: run `python backend/seed.py`
- [ ] Replace mock AI in `backend/app/services/ai_engine.py` with real Alibaba Cloud Model Studio `qwen2.5-vl-72b-instruct` client
- [ ] Set `MOCK_AI_ENGINE=false` in `backend/.env`
- [ ] Verify CORS in `backend/app/main.py` (`allow_origins=["*"]`)
- [ ] Run `python backend/test_scoring_local.py` and verify all 5 scoring branches pass
- [ ] Test `POST /api/v1/verify-packaging` with a real packaging photo via curl/Postman
- [ ] Verify response matches `API_CONTRACT.md` (keys, types, `bbox_2d: [ymin, xmin, ymax, xmax]` on 0–1000 scale)
- [ ] Confirm scan entry is logged to Supabase `scanned_logs`

**Exit condition:** A real image upload returns a contract-compliant JSON response with dynamic OCR extraction and print evaluation from Qwen2.5-VL.

---

## Phase 2 — Flutter Scaffolding & Camera Capture
**Goal:** Flutter app captures high-resolution packaging photo at 3x macro zoom and uploads it to the backend.
- [ ] Scaffold `mobile_app/` Flutter project per `ARCHITECTURE.md` layout
- [ ] Configure `mobile_app/pubspec.yaml` (`camera`, `http`, `permission_handler`, `google_fonts`)
- [ ] Configure camera and internet permissions in `AndroidManifest.xml` and `Info.plist`
- [ ] Build `lib/screens/camera_screen.dart`:
  - 3x macro zoom locked by default (with 1x/2x/3x toggle buttons)
  - Centered reticle guide frame for batch and 2D DataMatrix alignment
  - Shutter button with circular progress indicator
- [ ] Build `lib/services/api_service.dart`: multipart `POST` upload to `/api/v1/verify-packaging`

**Exit condition:** A photo captured in the mobile app successfully uploads to the backend and prints the full verification JSON to the debug console.

---

## Phase 3 — Result Screen & Bounding Box Overlay
**Goal:** Render inspection findings, risk scores, and visual defect boxes clearly for the user.
- [ ] Build `lib/widgets/bbox_painter.dart`: CustomPainter converting normalized `[ymin, xmin, ymax, xmax]` (0–1000 scale) to screen pixels, drawing red defect boxes with confidence labels
- [ ] Build `lib/screens/result_screen.dart`:
  - Image preview with defect bounding boxes overlaid
  - Color-coded verdict banner (🟢 GENUINE, 🟡 REVIEW RECOMMENDED, 🔴 SUSPECTED_COUNTERFEIT)
  - Layer 1 Database Verification breakdown card (GTIN, Batch, Expiry)
  - Layer 2 AI Micro-Texture breakdown card (Print Quality score, defect tags)
  - Technical summary text container
- [ ] Add error view handling for HTTP 400, 422, and 500 responses

**Exit condition:** Full flow runs on device/emulator (Capture → Analyze → View Result with overlays) for both genuine and counterfeit test packaging.

---

## Phase 4 — Cloud Hosting & Mobile Linking
**Goal:** Flutter app connects to a live public HTTPS endpoint instead of localhost.
- [ ] Deploy FastAPI backend container to Railway, Render, or Alibaba Cloud ECS
- [ ] Set production environment variables (`DATABASE_URL`, `DASHSCOPE_API_KEY`, `MOCK_AI_ENGINE=false`) on the host platform
- [ ] Update `baseUrl` in Flutter `api_service.dart` with the public HTTPS URL
- [ ] Verify endpoint uptime via `GET https://<deployed-url>/api/v1/health`

**Exit condition:** Mobile app running on a physical smartphone verifies packaging over cellular data/external Wi-Fi with no local servers running.

---

## Phase 5 — Product Polish & Standalone Build
**Goal:** Elevate UX from a prototype to a presentation-ready product.
- [ ] Add application icon and branded splash screen
- [ ] Add simple onboarding/tip overlay explaining lighting and macro distance
- [ ] Add network error retry button and camera focus feedback
- [ ] Build release Android binary: `flutter build apk --release`

**Exit condition:** Standalone release APK installed and running stably on a physical demo device.

---

## Phase 6 — Demonstration Assets & Pitch Deck
**Goal:** Complete materials required for submission and stage presentation.
- [ ] Assemble physical test dataset in `/dataset` (2 real pharmacy boxes, 2 synthetic inkjet printouts, 1 altered expiry sample)
- [ ] Record a 2-minute clean screen capture walkthrough of the full verification flow as an offline backup
- [ ] Finalize 10-slide presentation deck including DRAP correspondence traction
- [ ] Add project overview, architecture diagram, and setup instructions to root `README.md`

**Exit condition:** Complete demo kit tested and ready for judging presentation.