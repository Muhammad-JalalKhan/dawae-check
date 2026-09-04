# Agent Rules — Dawae-Check

Read `PROJECT_CONTEXT.md` first for orientation, then the relevant reference
doc (`API_CONTRACT.md`, `SCORING_LOGIC.md`, `DATABASE_SCHEMA.md`,
`ARCHITECTURE.md`) for the specific task at hand.

## Hard Constraints
1. **Stack is locked.** Flutter 3.x + FastAPI + PostgreSQL/Supabase + Qwen2.5-VL.
   Do not introduce a different framework, ORM, or state-management library
   without asking first.
2. **API contract is final.** Match `API_CONTRACT.md` exactly — field names,
   types, nesting, and the `bbox_2d` coordinate order `[y1, x1, y2, x2]`.
3. **Scoring formula is final.** Implement `SCORING_LOGIC.md` verbatim in one
   isolated module. Never inline the math elsewhere or change weights.
4. **Schema is final.** Match `DATABASE_SCHEMA.md`. If a migration is needed,
   propose it, don't silently alter columns.
5. **Never hardcode secrets.** API keys and DB connection strings go in `.env`
   (add to `.gitignore` if not already there), read via environment variables.
6. **Follow the folder layout** in `ARCHITECTURE.md` — don't restructure
   directories without asking.

## Before Writing Code
- Check `backend/app/schemas/` before writing any new Flutter HTTP call, so
  request/response shapes match what actually exists (not just the doc).
- If `backend/` doesn't run locally yet, flag that and prioritize fixing it
  before building more mobile screens against it.

## Code Style
- Python: type hints everywhere, Pydantic v2 models for all API I/O, black-formatted.
- Dart: null-safety on, widgets split into small reusable files (avoid 500-line
  screen files), use `http` or `dio` package consistently (pick one, don't mix).
- Commit messages: short, imperative (`Add camera macro lock`, not `added stuff`).

## When Unsure
Ask before:
- Adding a new dependency/package
- Changing anything in the four "final" docs above
- Restructuring folders
- Choosing between two reasonable implementation approaches with real tradeoffs

Don't ask before:
- Standard boilerplate (error handling, loading states, basic styling)
- Fixing an obvious bug in existing code
- Writing tests
