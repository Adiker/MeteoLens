# MeteoLens

MeteoLens is a web application for visualising public IMGW-PIB weather and
hydrological data for Poland. Stages 0-5 (research, documentation, backend
API, IMGW integration, and the frontend map UI) are implemented; **Stage 6
(quality: test coverage, attribution/data-integrity verification, and known
limitations)** is in progress. See [TASKS.md](TASKS.md) for the full staged
backlog.

The working package name is `meteolens`. Possible future product names:
PogodoScope, HydroMeteo Atlas, MeteoMapa PL.

## What It Will Do

- Show Poland as the main interactive map view.
- Display layers for synoptic stations, hydrological stations, meteorological
  stations, meteorological warnings, and hydrological warnings.
- Show measurement timestamp, retrieval timestamp, data delay, source, missing
  values, and processed-data notices.
- Provide simple and expert modes.
- Support search, "My location", station details, warning details, charts,
  exports, keyboard shortcuts, permalinked map state, and light/dark/system
  themes.

## Current Status

Implemented now:

- IMGW-PIB source research.
- Architecture decision record in documentation.
- Public backend API contract draft.
- UI/UX specification.
- Legal attribution rules.
- Implementation backlog and staged task list.
- FastAPI backend with `/health`, `/api/v1/sources`, map layers, stations,
  warnings, location summary, and CSV/JSON/GeoJSON exports backed by the cache.
- React/Vite map-first frontend: layer toggles, station markers, station and
  warning details (with mobile bottom sheet), station search, "My location",
  ECharts station chart, CSV/JSON/GeoJSON/PNG exports, URL permalinks, keyboard
  shortcuts, light/dark/system theme, simple/expert mode, and explicit
  loading/empty/stale/partial/error states.
- Docker Compose, `.env.example`, basic CI, lint, and tests.
- IMGW-PIB HTTP client, parser layer, normalized models, file cache, and parser
  tests for current synop/hydro/meteo/warning endpoints plus product manifests.

Not implemented yet: see [Known Limitations](#known-limitations) below.

## Data Sources

Primary source: IMGW-PIB public data service at
[danepubliczne.imgw.pl](https://danepubliczne.imgw.pl/).

The initial source set is documented in [DATA_SOURCES.md](DATA_SOURCES.md):

- current synoptic data,
- current hydrological data,
- current meteorological data,
- current meteorological warnings,
- current hydrological warnings,
- product/file API,
- archived warnings,
- measurement and observation archives.

## Quick Start

Run the backend locally:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install ".[dev]"
.venv/bin/uvicorn app.main:app --reload
```

Run the frontend locally:

```bash
cd frontend
npm install
npm run dev
```

The frontend reads the backend base URL from `VITE_API_BASE_URL` (default
`http://localhost:8000`). If port 8000 is taken by another app, run the backend
elsewhere and point the frontend at it: copy `frontend/.env.example` to
`frontend/.env.local`, set `VITE_API_BASE_URL=http://localhost:<port>`, and
restart `npm run dev`. With an empty cache the UI shows explicit empty/stale
states instead of mock data, so populate the backend cache to see live markers.

Run both with Docker Compose:

```bash
docker compose up --build
```

Local URLs:

- Frontend: `http://localhost:5173`
- Backend healthcheck: `http://localhost:8000/health`
- Backend source status: `http://localhost:8000/api/v1/sources`

## Planned Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, shadcn/ui, MapLibre GL,
  Apache ECharts, TanStack Query, Zustand.
- Backend: Python, FastAPI, Pydantic, httpx, scheduler, SQLite for MVP, Alembic
  with a migration path to PostgreSQL/PostGIS/TimescaleDB.
- Deployment: Docker Compose for local and small production deployments.

## Screenshots And Mockups

The Stage 5 map-first UI is implemented; screenshot assets under `docs/` are not
captured yet and should be added from a populated cache. The target layout is
specified in [UI_UX.md](UI_UX.md).

## Planned Exports

- CSV for selected station data.
- JSON for selected station or object details.
- GeoJSON for visible map objects.
- PNG for the current map view.
- PDF reports after MVP.

Every export must include IMGW-PIB attribution and, when applicable, a processed
data notice.

## Attribution

MeteoLens uses data from Instytut Meteorologii i Gospodarki Wodnej - Państwowy
Instytut Badawczy (IMGW-PIB). UI, exports, and documentation must identify
IMGW-PIB as the source. If MeteoLens normalizes, aggregates, interpolates, or
otherwise transforms data, the output must also say that IMGW-PIB data has been
processed.

See [LEGAL_ATTRIBUTION.md](LEGAL_ATTRIBUTION.md).

## Known Limitations

These are known, accepted gaps ahead of an MVP release — not bugs to silently
work around. Each one is either a documented backend constraint or an
intentional scope deferral; do not paper over them with mock/interpolated
data (see `AGENTS.md`).

- **No warning area polygons.** Meteorological/hydrological warnings carry
  TERYT codes and basin/province names but no geometry, so warnings render as
  a filterable list instead of map polygons
  (`missing_area_geometry_dataset`). Landing this needs a TERYT/basin geometry
  dataset; see `DATA_SOURCES.md`.
- **Synoptic stations have no coordinates.** `api/data/synop` does not return
  `lat/lon`, so synop stations appear in lists/details but are excluded from
  map markers (`missing_lat_lon`) until an official station coordinate
  dataset is added.
- **No time series, only a snapshot.** The station chart shows the latest
  cached value per metric, not history — the cache keeps one snapshot per
  station, not an archive. Multi-point charts need the archive/measurement
  endpoints (Stage 0 research already scoped these; not yet implemented).
- **Timeline/animation control is inert.** The bottom timeline UI is scaffolded
  but has nothing time-aware (archive or radar frames) to drive it yet.
- **Province/time-range quick filters are deferred.** These depend on the same
  area-geometry and archive-series work as the two points above.
- **No public cache-refresh endpoint.** The cache is populated by backend
  internals (scheduler/manual trigger), not a user-facing "refresh" API call;
  this was explicitly deferred from Stage 4 to a later stage.
- **Radar, GRIB, and other `product` API files are not parsed or rendered.**
  Only the product manifest listing is implemented; binary format decoding,
  projections, and tile rendering are post-MVP work (see `TROUBLESHOOTING.md`
  → "Radar And GRIB").
- **Some `product` IDs are listed but not retrievable.** The manifest can
  reference files that 404 at the detail endpoint; treat this as a source
  risk, not an application bug.
- **E2E tests run against seeded fixtures, not live IMGW-PIB.** `npm run
  test:e2e` seeds the backend cache from `backend/tests/fixtures` so CI does
  not depend on the real endpoint's availability or rate limits — it verifies
  the app's own request/response handling, not IMGW-PIB's live behavior.
- **No production security/licensing review.** Attribution and processed-data
  notices are implemented and tested, but deployers must still verify current
  IMGW-PIB terms before public or commercial use (see
  `LEGAL_ATTRIBUTION.md` → "Commercial And Public Use").

## Troubleshooting

For scoped gaps in the current release, see [Known Limitations](#known-limitations)
above. For runtime problems (port conflicts, CORS, source errors), see
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Development Checks

Backend:

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/pytest
```

Frontend:

```bash
cd frontend
npm run lint
npm test
npm run build
```

End-to-end (Playwright, drives a real backend + frontend against seeded
fixture data instead of live IMGW-PIB):

```bash
cd frontend
npx playwright install chromium  # first run only
npm run test:e2e
```
