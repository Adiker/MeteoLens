# CLAUDE.md - MeteoLens

This is the concise working guide for Claude/Codex in this repository. Mandatory
agent rules live in `AGENTS.md`; treat that file as authoritative.

## Project Snapshot

- **What:** Web application for visualising public IMGW-PIB meteorological and
  hydrological data for Poland.
- **Status:** Stages 0-12 are implemented and documented: FastAPI cache-backed
  APIs, IMGW client/parser/cache layer, React/Vite/MapLibre frontend,
  production Compose setup, local observation history, geometry pipeline shell,
  product timeline metadata, PWA shell, browser-local power-user tools, and
  public-alpha release polish (recorded smoke tests, populated-cache
  screenshots, release checklist — see `docs/release/`). Stages 13-16 are
  planned next and must not be treated as implemented.
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
  checklist under `docs/release/` and `docs/screenshots/`). Do not mark
  Stage 13-16 work (reviewed datasets, product rendering, archive backfill,
  generated SDK) complete until the repo contains the implementation and
  matching docs/tests.
