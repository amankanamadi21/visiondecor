# VisionDecor

Context-Aware AI Interior Design Recommendation System with Layout Optimization.

This repo was built incrementally, one approved decision at a time — see `PLAN.md` for the
full project decision log, architecture, and report-inconsistency tracking. Every AI-driven
number in this project is either measured (and reproducible via the scripts in `evaluation/`),
clearly labeled `estimated`/`user-provided`, or (for anything still a placeholder) clearly labeled
`MOCK` — nothing is presented as more certain than it actually is.

**Current status: the full pipeline is implemented and tested end-to-end.** Real photo upload →
real furniture detection + architectural segmentation → real zero-shot style recognition → a
RAG-grounded recommendation engine over a seeded catalog → a from-scratch Simulated Annealing
layout optimizer → photorealistic visualization (with automatic provider fallback) → structured
feedback → refinement → side-by-side comparison → PDF export. CPU-only throughout (no GPU
required, no model fine-tuning) per this project's own stated hardware constraint.

## Prerequisites

- Python 3.12 (a `.venv` using this version is expected at the repo root)
- Node.js 18+ and npm
- Docker (for PostgreSQL + pgvector)
- No GPU needed — every model here runs pretrained, CPU-only

## First-time setup

```bash
# 1. Backend virtualenv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 2. Environment
cp .env.example .env
cp frontend/.env.example frontend/.env
# Render-provider keys (GEMINI_API_KEY / CLOUDFLARE_ACCOUNT_ID+TOKEN) are optional —
# leave them blank to get the deterministic floor-plan visualization only,
# no photorealistic render. See "Render providers" below.

# 3. Database
docker compose up -d db
alembic upgrade head
python scripts/seed_catalog.py       # furniture catalog (30 real products, data_source='REAL')
python scripts/seed_principles.py    # design-principles corpus + embeddings, for RAG rationale

# 4. Frontend
cd frontend && npm install && cd ..
```

The first real photo upload downloads ~50MB of pretrained model weights (YOLOv8n, SegFormer-B0,
CLIP-RN50) on demand — expect a one-time delay there, not a hang.

## Running it

```bash
# Terminal 1 — backend
source .venv/bin/activate
FLASK_APP=backend.app:create_app flask run --port 5000

# Terminal 2 — frontend
cd frontend && npm run dev -- --port 5173
```

Open http://localhost:5173, register an account, and walk through: create a design → pick a room
type → either choose a sample room (labeled demo data, disclosed as such throughout) or upload
your own photo with its real width/length → set style/colors/budget → generate → see the
recommendation (with real per-item score breakdowns and RAG-cited rationale), the layout (hard
constraints + a 5-term weighted score), and a visualization (photorealistic if a render provider
key is configured, otherwise the always-available deterministic floor plan) → optionally confirm a
detected item's real size/position to place it for real in the layout → submit feedback in plain
English to get a refined iteration → compare iterations side by side → export the finished design
as a PDF.

Only running one command at a time? Background the backend in the same terminal instead of using
two:

```bash
source .venv/bin/activate
FLASK_APP=backend.app:create_app flask run --port 5000 &
cd frontend && npm run dev -- --port 5173
```

### Running it via Docker (backend + frontend, alongside the existing `db` service)

```bash
docker compose up --build
# first run only, once containers are up:
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed_catalog.py
docker compose exec backend python scripts/seed_principles.py
```

Same URLs as above (`:5173` frontend, `:5000` backend). Source is bind-mounted into both
containers, so code changes still hot-reload without a rebuild — only changing
`requirements.txt`/`package.json` needs `--build` again. Pretrained model weights persist across
container restarts via named volumes (`visiondecor_hf_cache`, `visiondecor_torch_cache`,
`visiondecor_ultralytics_config`), so they aren't re-downloaded every time.

**Honesty note:** the `docker-compose.yml`/`Dockerfile` setup is verified for structure and
correctness (`docker compose config` resolves `DATABASE_URL` to the `db` service correctly; the
frontend image builds and serves real content) — but the backend image's build has not been
verified to fully complete on this project's development machine, where `pip install`'s download
of large ML dependencies (torch et al.) repeatedly stalled inside Docker Desktop's VM specifically
(the same packages install fine in a local venv — see PLAN.md for the full account). If
`docker compose build backend` stalls for you too, restarting Docker Desktop often clears this
class of VM networking issue; otherwise fall back to the venv + npm instructions above, which are
fully verified.

### Render providers (optional, decision D003)

Photorealistic rendering needs at least one of these; without any, the app still works fully,
using the deterministic floor plan as the visualization (never a hard requirement, per this
project's own design):

| Provider | Free tier | Structure-preserving? |
|---|---|---|
| Gemini (`GEMINI_API_KEY`) | Free tier currently grants 0 image-generation quota (a policy change discovered live, 2026-09-07) — implemented and wired correctly, not currently usable without billing | Yes — real image editing |
| Cloudflare Workers AI (`CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN`) | 10,000 free "neurons"/day, no card | No — text-to-image only; the UI discloses this per-render |
| Hugging Face (`HUGGINGFACE_API_TOKEN`) | Free tier, no card | No — text-to-image only; same disclosure |

Tried in that order; the first one configured and working serves the request, so having all three
configured just makes the render path more resilient, not different in kind.

## Verifying it

```bash
source .venv/bin/activate
pytest                               # 128 tests: auth, uploads, jobs, style recognition,
                                      # RAG recommendation, layout optimization, real CV
                                      # detection/segmentation, user-confirmed geometry,
                                      # visualization fallback (Gemini/Cloudflare/HF),
                                      # feedback loop, comparison

cd frontend && npx tsc --noEmit      # frontend type-checks cleanly
cd frontend && npm run build         # production build succeeds
cd frontend && npm run lint          # oxlint
```

Measured results (real numbers, reproducible via `evaluation/`, not estimated):

```bash
python -m evaluation.run_layout_study         # SA vs. random/greedy baselines
python -m evaluation.run_recommendation_study # budget compliance / style-match / space-fit rates
python -m evaluation.run_style_study          # zero-shot CLIP accuracy on a real labeled test set
python -m evaluation.run_detection_study      # YOLO mAP@50/precision/recall on real COCO photos
```

Manual checks worth doing after any auth/upload change:
- Register, then in devtools confirm `vd_access_token` is `HttpOnly` (not readable from
  `document.cookie`) and `vd_csrf_token` is not.
- Upload a `.txt` file renamed to `.jpg` — must be rejected (`415`), not silently accepted or
  crash with a stack trace.
- Log in as a second user and try `GET /api/sessions/<first user's id>` — must be `404`, not
  `403` (never confirm the id exists to a non-owner).

## Project structure

```
backend/    Flask app, models, API routes, auth/upload/job services
ai/         room_analysis (real CV: detection.py, segmentation.py), style_recognition,
            recommendation (RAG + scoring), layout_optimization (Simulated Annealing),
            visualization (provider fallback chain + deterministic floor plan)
database/   Alembic migrations
frontend/   React + TypeScript (Vite)
scripts/    one-off/admin scripts (catalog + design-principles seeding)
tests/      pytest suite
evaluation/ measured-metric scripts (layout, recommendation, style, detection)
datasets/   gitignored — evaluation datasets (Houzz styles, COCO subset), downloaded on demand
```

## Known, deliberate limitations

- **Job runner** is a single-process thread pool, not a real queue (Redis/RQ) — a stated
  limitation against the report's NFR-5 (Scalability), not silently presented as production-scale.
- **`furniture_catalog` rows are real, purchasable products** (`data_source='REAL'`), manually
  researched from real Indian retailers (IKEA India, Urban Ladder, Pepperfry, Home Centre, Wakefit,
  Obeetee, Homesake, Amazon.in) — real price, real dimensions, real product link, each stamped
  `price_verified_at` so a stale price reads as stale, not as live. 11 of 30 items are the closest
  in-stock real match rather than an exact match to the original concept, or have one
  retailer-unstated dimension estimated — every such deviation is flagged inline in
  `scripts/seed_catalog.py` and in `PLAN.md`, never silently substituted. One deliberate exception:
  `image_url` is still a placeholder stock photo, not a hotlinked retailer photo (avoids third-party
  image ToS/copyright issues) — the "View real product ↗" link, not the thumbnail, is what actually
  points at the genuine item.
- **A detection's pixel bounding box alone never becomes a real position or size** — a single 2D
  photo has no depth information to derive one honestly. By default, confidently-detected chair/
  couch/bed/table items only reduce the estimated free floor space (using the catalog's own real
  category averages). The one exception: the user can explicitly confirm an item's real width/
  depth/height and click its position on a to-scale room outline, which places it as a genuine
  existing object the layout optimizer plans around — every number in that path is user-provided,
  never derived from the pixel bbox.
- **Detection recall is measured, not hidden**: 76% precision / 30% recall at the app's operating
  threshold (mAP@50 0.53) — it misses many small/occluded objects, a real, measured trade-off of
  the smallest/fastest YOLO variant chosen for CPU inference.
- **Gemini's free tier currently grants zero image-generation quota** (confirmed live, not
  assumed); Cloudflare covers the free-tier gap but is not structure-preserving, disclosed
  per-render in the UI.
- **No shareable public link yet** — only a personal PDF export. A public link is a genuinely new
  privacy surface (permanent vs. revocable, what data is safe to expose) not yet decided.
- **Style/detection evaluation uses public datasets, not this project's own users' photos** — see
  `PLAN.md` for the exact evaluation methodology and what remains "not yet measured."
