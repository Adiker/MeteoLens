# MeteoLens

MeteoLens is a web application for visualising public IMGW-PIB weather and
hydrological data for Poland. Stages 0-11 (research, documentation, backend
API, IMGW integration, the frontend map UI, quality/test hardening, production
deployment, observation history, geometry datasets, product timeline, and
PWA/power-user features) are implemented. See [TASKS.md](TASKS.md) for the
full staged backlog. Stages 12-16 are planned next and are not implemented yet.

The working package name is `meteolens`. Possible future product names:
PogodoScope, HydroMeteo Atlas, MeteoMapa PL.

## What It Does

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
- Docker Compose, `.env.example`, CI (backend, frontend, and E2E jobs), lint,
  and tests.
- IMGW-PIB HTTP client, parser layer, normalized models, file cache, and parser
  tests for current synop/hydro/meteo/warning endpoints plus product manifests.
- Live IMGW startup cache refresh (`METEOLENS_SYNC_ON_STARTUP`) and a periodic
  in-process refresh scheduler (`METEOLENS_REFRESH_ENABLED` with
  `METEOLENS_REFRESH_*_SECONDS` intervals), both enabled by default in Docker
  Compose, with their own refresh tests.
- Stage 6 quality work: expanded backend/frontend test coverage, a Playwright
  E2E suite, and verified attribution/missing-value handling (see
  [Known Limitations](#known-limitations)).
- Stage 7 production deployment: nginx + runtime images, production Compose
  file, and hardening checklist — see [DEPLOYMENT.md](DEPLOYMENT.md).
- Stage 8 observation history: SQLite history persisted on each successful
  IMGW refresh with configurable retention
  (`METEOLENS_OBSERVATION_RETENTION_DAYS`), a time-series API with metric,
  time-range, `interval`, and `limit` parameters plus `series_kind`
  snapshot-fallback metadata, station comparison and rankings endpoints,
  time-range exports, and a station chart that renders real multi-point line
  series when history exists.
- Stage 9 geometry and spatial warnings: a manifest-driven local geometry
  cache (`data/geometry/`, `METEOLENS_GEOMETRY_DIR`,
  `/api/v1/geometry/datasets`), TERYT/basin code-to-polygon mapping for
  warning map layers and warning details, polygon-based "My location" warning
  matching, and province/county/basin warning filters with explicit
  unresolved-geometry metadata (see `docs/geometry/GEOMETRY_SOURCES.md`).
- Stage 10 product timeline: IMGW product ID research
  (`docs/products/PRODUCT_RESEARCH.md`), product catalog and frame metadata
  APIs (`/api/v1/products`, `/api/v1/products/{id}/frames`,
  `/api/v1/map/timeline`), and a frontend timeline bar with play/step
  controls and explicit metadata-only / not-renderable labels.
- Stage 11 PWA and power-user features: cache freshness and
  warning-vs-station comparison endpoints, an expert-mode power-user panel
  (saved locations, saved map views, dashboard widgets, local alert rules,
  freshness monitor, advanced filters — all browser-local storage), and a
  minimal installable PWA shell.

Planned next:

- Stage 12 public alpha release polish: reproducible local and production smoke
  tests, populated-cache screenshots from real IMGW-backed data, README alpha
  status, a `v0.1.0-alpha` checklist, and documentation consistency fixes.
- Stage 13 reviewed geometry dataset MVP: legally reviewed administrative,
  basin, and station-coordinate datasets with validation, tests, and explicit
  unresolved-geometry states.
- Stage 14 radar/product rendering MVP: one realistic renderable product layer
  path, retention limits, renderable-layer API metadata, and timeline playback
  that never labels metadata-only frames as rendered data.
- Stage 15 historical archive backfill: opt-in, bounded, rate-limited archive
  import for at least one legally and technically clear IMGW observation source.
- Stage 16 public API, SDK, and power-user exports: stabilized API docs,
  TypeScript client preparation, example scripts, stronger exports, and
  responsible-use/versioning notes.

Remaining gaps: see [Known Limitations](#known-limitations) below.

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
restart `npm run dev`. To populate the backend cache with live IMGW data during
manual backend startup, set `METEOLENS_SYNC_ON_STARTUP=true` before running
Uvicorn. With an empty cache the UI shows explicit empty/stale states instead of
mock data.

Run both with Docker Compose:

```bash
docker compose up --build
```

Docker Compose enables `METEOLENS_SYNC_ON_STARTUP=true`, so the backend fetches
the configured live IMGW sources and writes the normalized file cache before the
frontend is marked ready. It also enables `METEOLENS_REFRESH_ENABLED=true`, so
the backend keeps re-fetching each source on its configured
`METEOLENS_REFRESH_*_SECONDS` interval while it runs.

Local URLs:

- Frontend: `http://localhost:5173`
- Backend healthcheck: `http://localhost:8000/health`
- Backend source status: `http://localhost:8000/api/v1/sources`

Production smoke test (nginx + runtime backend image):

```bash
cp deploy/.env.production.example .env.production
docker compose --env-file .env.production -f docker-compose.prod.yml up --build
```

Then open `http://localhost:8080`. See [DEPLOYMENT.md](DEPLOYMENT.md) and
[deploy/PRODUCTION_CHECKLIST.md](deploy/PRODUCTION_CHECKLIST.md).

## Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, shadcn/ui, MapLibre GL,
  Apache ECharts, TanStack Query, Zustand.
- Backend: Python, FastAPI, Pydantic, httpx, scheduler, SQLite for MVP, Alembic
  with a migration path to PostgreSQL/PostGIS/TimescaleDB.
- Deployment: Docker Compose for local and small production deployments.

## Screenshots And Mockups

The map-first UI is implemented; screenshot assets under `docs/screenshots/`
are not captured yet — follow the capture instructions in
[docs/screenshots/README.md](docs/screenshots/README.md) against a populated
live cache. Public-alpha screenshots and README references are planned in
Stage 12 and must use real IMGW-backed data, not fixtures. The target layout is
specified in [UI_UX.md](UI_UX.md).

## Exports

- CSV for selected station data, including selected time ranges.
- JSON for selected station or object details.
- GeoJSON for visible map objects.
- PNG for the current map view.
- PDF reports remain planned for after MVP.

Every export must include IMGW-PIB attribution and, when applicable, a processed
data notice.

## Attribution

MeteoLens uses data from Instytut Meteorologii i Gospodarki Wodnej - Państwowy
Instytut Badawczy (IMGW-PIB). UI, exports, and documentation must identify
IMGW-PIB as the source. If MeteoLens normalizes, aggregates, interpolates, or
otherwise transforms data, the output must also say that IMGW-PIB data has been
processed.

See [LEGAL_ATTRIBUTION.md](LEGAL_ATTRIBUTION.md).

## License

MeteoLens code and documentation are released under the
[MIT License](LICENSE). Source weather and hydrological data remains governed
by the applicable IMGW-PIB terms and any other source-specific terms.

## Known Limitations

These are known, accepted gaps ahead of an MVP release — not bugs to silently
work around. Each one is either a documented backend constraint or an
intentional scope deferral; do not paper over them with mock/interpolated
data (see `AGENTS.md`).

- **Warning polygons need locally installed geometry datasets.** The Stage 9
  geometry pipeline (manifest, loader, polygon mapping, spatial matching,
  province/county/basin filters) is implemented, but the repository ships an
  empty `data/geometry/manifest.json` — every candidate TERYT/basin dataset
  is still `planned` pending source/legal review. Until reviewed GeoJSON is
  placed under `data/geometry/`, warnings render as a filterable list and
  report `missing_area_geometry_dataset`. See
  `docs/geometry/GEOMETRY_SOURCES.md`.
- **Synoptic stations have no coordinates.** `api/data/synop` does not return
  `lat/lon`, so synop stations appear in lists/details but are excluded from
  map markers (`missing_lat_lon`). The `synop_stations` coordinate
  reconciliation dataset is designed but still `planned` in
  `docs/geometry/GEOMETRY_SOURCES.md`, pending an officially cleared station
  metadata source.
- **Observation history starts empty and is local-only.** Time series are
  persisted to SQLite from this deployment's own IMGW refreshes; there is no
  backfill from the IMGW measurement archives. Fresh deployments serve
  single-point snapshots (`series_kind: "snapshot"`) until enough refresh
  cycles accumulate, and retention is capped by
  `METEOLENS_OBSERVATION_RETENTION_DAYS`.
- **Timeline/animation for products.** When cached product frame manifests exist,
  the bottom timeline shows frame metadata with play/step controls and explicit
  “metadata only / not renderable on map” labels. Binary radar/GRIB rendering on
  the map is still deferred.
- **Province/county/basin filters only work with installed geometry.** The
  warning area filters shipped in Stage 9 resolve against the local geometry
  cache, so they return no matches until reviewed datasets are installed (see
  the warning-polygon limitation above).
- **No public cache-refresh endpoint.** Docker Compose populates the cache at
  backend startup via `METEOLENS_SYNC_ON_STARTUP=true` and keeps it fresh with
  the periodic scheduler (`METEOLENS_REFRESH_ENABLED=true`); there is still no
  user-facing "refresh data" API call.
- **Radar, GRIB, and other `product` API files are not parsed or rendered on the
  map.** Stage 10 documents product IDs, exposes frame metadata APIs, and adds a
  timeline shell. Binary format decoding, projections, and tile rendering remain
  post-MVP work (see `docs/products/PRODUCT_RESEARCH.md` and
  `docs/products/RASTER_PIPELINE.md`).
- **Some `product` IDs are listed but not retrievable.** Research on 2026-07-01
  found 32/42 manifest IDs returning 404 at the detail endpoint; see
  `docs/products/PRODUCT_RESEARCH.md` for the full classification.
- **E2E tests run against seeded fixtures, not live IMGW-PIB.** `npm run
  test:e2e` seeds the backend cache from `backend/tests/fixtures` so CI does
  not depend on the real endpoint's availability or rate limits — it verifies
  the app's own request/response handling, not IMGW-PIB's live behavior.
- **Expert mode tools.** Saved locations, saved map views, local alert rules,
  freshness monitor, and warning-vs-station comparison live in the advanced panel
  (browser-local storage). MeteoLens is not an official alerting system.
- **Minimal PWA shell.** Manifest and service worker cache static assets only; IMGW
  data still requires a live backend connection.
- **Source-terms verification stays with the deployer.** Attribution and
  processed-data notices are implemented and tested, but deployers must still
  verify current IMGW-PIB terms before public or commercial use (see
  `LEGAL_ATTRIBUTION.md` → "Commercial And Public Use" and
  [deploy/PRODUCTION_CHECKLIST.md](deploy/PRODUCTION_CHECKLIST.md)).

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
