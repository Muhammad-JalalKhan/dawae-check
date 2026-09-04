# Dawae-Check — Project Context

**Tagline:** AI-Powered Medicine Verification at the Point of Care
**Track:** Healthcare (MedTech & Drug Safety) — AI Hackathon Pakistan 2026
**Users:** Pharmacists, dispensary operators, field health workers, consumers

## The Problem
Counterfeit medicine is common in informal supply chains. Standard QR/barcode
verification fails because counterfeiters simply photocopy real QR codes onto
fake boxes — the code scans "valid" even though the medicine isn't.

## The Solution
A **Dual-Gate Verification Pipeline**: the user photographs packaging (3x macro),
and the system checks it two independent ways. Both must pass for a GENUINE verdict.

```
[3x Macro Photo] → [Qwen2.5-VL Vision Model]
                          │
        ┌─────────────────┴─────────────────┐
        ▼                                     ▼
  Layer 1: Database Gate              Layer 2: Visual Micro-Texture Gate
  - OCR: GTIN, Batch, Expiry, Reg     - Halftone/inkjet dot detection
  - Lookup in batch_registry DB       - Typography edge blur/bleed
  - Flags tampered dates/clones       - Barcode ISO 15415 degradation
        │                                     │
        └─────────────────┬─────────────────┘
                          ▼
                Composite Scoring Engine
                GENUINE / SUSPICIOUS / COUNTERFEIT
```

Full technical detail lives in the sibling docs — this file is orientation only.
See: `ARCHITECTURE.md`, `API_CONTRACT.md`, `SCORING_LOGIC.md`, `DATABASE_SCHEMA.md`.

## Tech Stack (locked — do not swap)
- **AI Vision:** Alibaba Cloud Model Studio, Qwen2.5-VL (72B / 7B), OpenAI-compatible endpoint
- **Backend:** FastAPI (Python 3.11+), Pydantic v2, SQLAlchemy, Uvicorn
- **Database:** PostgreSQL / Supabase
- **Mobile:** Flutter 3.x — camera macro zoom, custom canvas bbox overlays
- **Deploy:** Docker, Railway or Alibaba Cloud ECS

## Current Status
- ✅ Backend scaffolded and pushed by teammate (see `backend/`)
- ⬜ Backend not yet verified end-to-end (test this first — see TASKS.md)
- ⬜ Mobile app (`mobile_app/`) — not started, this is the primary build target
- ⬜ Deployment
- ⬜ Dataset + pitch deck

## Repo Map
```
dawae-check/
├── backend/            # FastAPI + Qwen2.5-VL integration (exists)
├── mobile_app/          # Flutter app (to build)
├── dataset/             # real vs counterfeit test images
├── docs/                # this folder + pitch deck
└── *.md                 # context files for agent (this set)
```

## Working Agreement For The Agent
1. Never invent new API fields — the contract in `API_CONTRACT.md` is final.
2. Never change the scoring formula in `SCORING_LOGIC.md` without being asked.
3. Always check `backend/app/schemas` before writing a new Flutter API call.
4. Follow the folder structure in `ARCHITECTURE.md` section "Repo Layout."
5. Ask before introducing a new dependency/library not already in the stack.
