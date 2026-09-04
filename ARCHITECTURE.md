# Architecture — Dawae-Check

## Data Flow
1. User opens Flutter app, locks camera to 3x macro.
2. User captures photo of medicine packaging.
3. App sends `multipart/form-data` POST to `/api/v1/verify-packaging` with `file`, `device_id`, `facility_id`.
4. FastAPI backend forwards image to Qwen2.5-VL (Alibaba Model Studio).
5. Model returns OCR text + defect detections with `bbox_2d` coordinates on a 0-1000 scale.
6. Backend executes:
   - Layer 1 (`app/services/db_gate.py`): verify extracted GTIN/Batch/Expiry against Supabase `batch_registry` and check clone anomalies via `app/services/clone_detection.py`.
   - Layer 2 (`app/services/ai_engine.py`): evaluates physical print artifacts (halftone dots, edge blur).
7. Backend computes `S_final` via `app/services/scoring.py`, assigns verdict, writes audit record to `scanned_logs`, and returns JSON.
8. Flutter result screen parses JSON, renders verdict badge (🟢/🟡/🔴), and draws bounding boxes using `bbox_painter.dart`.

## Repo Layout (Authoritative — matches existing backend)
dawae-check/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/       # verification & batch endpoints
│   │   ├── core/config.py          # pydantic settings (.env)
│   │   ├── db/session.py           # asyncpg Supabase connection
│   │   ├── models/                 # batch_registry.py, manufacturer.py, scanned_log.py
│   │   ├── schemas/                # pydantic request/response models
│   │   ├── services/
│   │   │   ├── ai_engine.py        # Qwen2.5-VL inference service
│   │   │   ├── clone_detection.py  # multi-facility clone tracking
│   │   │   ├── db_gate.py          # Layer 1 deterministic database checks
│   │   │   └── scoring.py          # S_final calculation
│   │   └── main.py                 # FastAPI app entrypoint & CORS
│   ├── requirements.txt
│   ├── Dockerfile
│   └── seed.py                     # seed database script
├── mobile_app/
│   ├── lib/
│   │   ├── screens/camera_screen.dart
│   │   ├── screens/result_screen.dart
│   │   ├── widgets/bbox_painter.dart
│   │   ├── services/api_service.dart
│   │   └── main.dart
│   └── pubspec.yaml
├── dataset/
├── docs/
├── .gitignore
└── README.md

## Component Responsibilities
| Component | Responsibility | Must NOT do |
|---|---|---|
| `camera_screen.dart` | Capture 3x macro image, upload | Business logic, scoring |
| `result_screen.dart` | Render verdict + score + defects | Re-implement scoring math |
| `bbox_painter.dart` | Draw `[y1,x1,y2,x2]` boxes on canvas | Fetch data itself |
| `ai_engine.py` | Call Qwen2.5-VL, parse response | Direct DB writes |
| `routes.py` | Orchestrate layer 1 + layer 2, return contract JSON | Contain scoring math inline (import from a scoring module) |
| `db_models.py` | ORM definitions matching `DATABASE_SCHEMA.md` | Diverge from the DDL |

## External Dependencies
- Alibaba Cloud Model Studio API key (env var, never hardcoded)
- PostgreSQL/Supabase connection string (env var)
- Ngrok (local mobile-to-backend dev only, not production)
