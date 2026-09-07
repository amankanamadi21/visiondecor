# VisionDecor

Context-Aware AI Interior Design Recommendation System with Layout Optimization.

This repo is being built incrementally, one approved decision at a time — see
`PLAN.md` (symlinked from the session's plan file, or copy it in) for the full
project decision log, architecture, and report-inconsistency tracking.

**Current status: Batch 1 — Backend Foundation.** Auth, room-image upload +
validation, session management, and a background job runner are implemented
and tested. The AI pipeline itself (room analysis, style recognition,
recommendation, layout optimization, visualization) is **not yet implemented**
— see `backend/services/pipeline_stages.py`, which raises a clear
`NotImplementedError` for each of those stages rather than faking a result.

## Prerequisites

- Python 3.12 (a `.venv` using this version is expected at the repo root)
- Node.js 18+ and npm
- Docker (for PostgreSQL + pgvector)

## First-time setup

```bash
# 1. Backend virtualenv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. Environment
cp .env.example .env
cp frontend/.env.example frontend/.env

# 3. Database
docker compose up -d db
alembic upgrade head
python scripts/seed_catalog.py

# 4. Frontend
cd frontend && npm install && cd ..
```

## Running it

```bash
# Terminal 1 — backend
source .venv/bin/activate
FLASK_APP=backend.app:create_app flask run --port 5000

# Terminal 2 — frontend
cd frontend && npm run dev -- --port 5173
```

Open http://localhost:5173, register an account, and walk through: create a
design → pick a room type → upload a photo → watch the preprocess job finish.
That's the full extent of what's implemented so far, and the app says so on
screen rather than pretending otherwise.

## Verifying it

```bash
source .venv/bin/activate
pytest                      # 21 tests: auth, session ownership, upload
                             # validation (magic bytes, size, corruption),
                             # CSRF, cross-user authorization, job lifecycle

cd frontend && npx tsc -b --noEmit   # frontend type-checks cleanly
```

Manual checks worth doing after any auth/upload change:
- Register, then in devtools confirm `vd_access_token` is `HttpOnly` (not
  readable from `document.cookie`) and `vd_csrf_token` is not.
- Upload a `.txt` file renamed to `.jpg` — must be rejected (`415`), not
  silently accepted or crash with a stack trace.
- Log in as a second user and try `GET /api/sessions/<first user's id>` —
  must be `404`, not `403` (never confirm the id exists to a non-owner).

## Project structure

```
backend/    Flask app, models, API routes, auth/upload/job services
ai/         room_analysis, style_recognition, recommendation,
            layout_optimization, visualization — one package per report layer
database/   Alembic migrations
frontend/   React + TypeScript (Vite)
scripts/    one-off/admin scripts (e.g. catalog seeding)
tests/      pytest suite
evaluation/ metric scripts (populated once Batch 2/3 AI components exist)
```

## Known, deliberate limitations (Batch 1)

- The background job runner is a single-process thread pool, not a real
  queue (Redis/RQ). Fine for a solo demo; documented as a stated limitation
  against the report's NFR-5 (Scalability), not silently presented as
  production-scale.
- `furniture_catalog` rows are mock data — every row has `data_source='MOCK'`,
  enforced by the model default and checked in the seed script.
