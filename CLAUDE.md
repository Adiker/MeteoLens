# CLAUDE.md - MeteoLens

This is the concise working guide for Claude/Codex in this repository. Mandatory
agent rules live in `AGENTS.md`; treat that file as authoritative.

## Project Snapshot

- **What:** Web application for visualising public IMGW-PIB meteorological and
  hydrological data for Poland.
- **Status:** Stages 0-18 are implemented and documented: FastAPI cache-backed
  APIs, IMGW client/parser/cache layer, React/Vite/MapLibre frontend,
  production Compose setup, local observation history, reviewed geometry
  pipeline, product timeline metadata plus COSMO 2 m temperature rendering,
  PWA shell, browser-local power-user tools, public-alpha release polish,
  bounded daily SYNOP archive backfill, public API exports, and the repo-local
  TypeScript API client, and Stage 18 reviewed WMO OSCAR/Surface synop station
  coordinates. Stages 19-26 are planned only: public-internet security,
  production observability/backup/recovery, current-main release validation,
  hydro basin geometry, hydrological archive backfill, warning history,
  performance/scalability hardening, and PDF reports remain future work until
  their own implementation, docs, and tests land.
- **Frontend plan:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui, MapLibre
  GL, ECharts, TanStack Query, Zustand.
- **Backend plan:** Python FastAPI, Pydantic, httpx, scheduler, cache, SQLite
  for MVP with a PostgreSQL/PostGIS/TimescaleDB migration path.
- **Main constraint:** real public IMGW-PIB data only; no final mock
  implementation.

## Read First

- `AGENTS.md` - mandatory workflow and guardrails.
- `DATA_SOURCES.md` - source endpoints, fields, formats, risks, parser status.
- `LEGAL_ATTRIBUTION.md` - attribution and processed-data rules.
- `ARCHITECTURE.md` - technical design.
- `TASKS.md` - ordered implementation work.
- `API_CONTRACT.md` - backend API expected by the frontend.
- `UI_UX.md` - map-first UI behavior.

## Common Commands

Backend:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install ".[dev]"
.venv/bin/ruff check .
.venv/bin/pytest
.venv/bin/uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run lint
npm test
npm run build
npm run dev
```

Full stack:

```bash
docker compose up --build
```

## Local Development

The frontend expects `VITE_API_BASE_URL`, defaulting to `http://localhost:8000`.
The backend reads `METEOLENS_*` environment variables; see `.env.example`.

## Tests

Backend tests use pytest and FastAPI TestClient. Frontend tests use Vitest,
Testing Library, and jsdom. Parser fixtures live under `backend/tests/fixtures`
and must stay test-only.

## Documentation Rules

- Public API changes update `API_CONTRACT.md`.
- Source/parser changes update `DATA_SOURCES.md`.
- UI behavior changes update `UI_UX.md`.
- Attribution or legal changes update `LEGAL_ATTRIBUTION.md`.
- End-user behavior and troubleshooting update `README.md`.

## Agent Working Notes

- Do not fetch IMGW directly from the browser in the final architecture; use the
  backend cache/API.
- Never turn `null` into `0`.
- Keep raw source metadata available for expert mode.
- Public cache refresh is handled by startup sync and the scheduler; there is no
  user-facing refresh endpoint yet.
- Stage 12 release polish is done (smoke-test record, screenshots, alpha
  checklist under `docs/release/` and `docs/screenshots/`). Stage 13 reviewed
  geometry is done (import CLI, bundled PRG datasets, docs under
  `docs/geometry/`); never edit `data/geometry/manifest.json` by hand — use
  `python -m app.geometry.import_cli`. Stages 14-16 are also implemented:
  product rendering is limited to the reviewed COSMO path, daily SYNOP archive
  backfill is opt-in and bounded, and the generated SDK/examples live under
  `packages/` and `examples/`. Stage 18 bundles reviewed WMO OSCAR/Surface
  synop station coordinates. Stage 19-26 tasks are unchecked planning items.
  Do not mark future work such as `hydro_basins`, hydrological archive imports,
  warning history, PDF reports, or radar rendering as implemented until the repo
  contains matching implementation, docs, tests, and source/legal review.
