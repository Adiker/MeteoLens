# CHANGELOG

All notable changes to MeteoLens will be documented in this file.

## Unreleased

- Added Stage 13 reviewed geometry dataset MVP: a format_version 2 geometry
  manifest with full source/legal review metadata enforced by the loader,
  strict GeoJSON validation (structure, geometry types, required properties,
  TERYT coverage, Poland bounds), a geometry import CLI
  (`python -m app.geometry.import_cli`), bundled reviewed PRG © GUGiK
  voivodeship and county polygons under `data/geometry/` (meteo warning
  polygons and province/county filters now work out of the box), a
  reproducible PRG conversion script
  (`scripts/geometry/convert_prg_shapefiles.py`), reviewed-source synop
  coordinate enrichment with a `coordinate_source` field, and expanded
  backend/frontend geometry tests. Hydro basin geometry and the synop
  coordinate dataset remain planned pending source review.
- Added Stage 12 public alpha release polish: recorded local and production
  smoke tests against live IMGW-PIB data
  (`docs/release/SMOKE_TEST_2026-07-03.md`), a repeatable browser smoke script
  (`frontend/scripts/smoke.mjs`) that also captures README screenshots,
  populated-cache screenshots under `docs/screenshots/`, a public-alpha status
  section in `README.md`, a `v0.1.0-alpha` release checklist
  (`docs/release/RELEASE_CHECKLIST_v0.1.0-alpha.md`), and a root
  `.dockerignore` fixing the production frontend build when the local
  `./data` bind mount contains container-owned cache files.
- Added documentation-only planning for Stages 12-16: public alpha release
  polish, reviewed geometry dataset MVP, radar/product rendering MVP,
  historical archive backfill, and public API/SDK/power-user export work.
- Clarified that populated-cache README screenshots are still pending Stage 12
  release polish, while Stage 7 only documented the capture requirements.
- Added Stage 11 power-user tooling: local saved locations/views, dashboard
  widget layout, local alert rules with official-warning disclaimer, freshness
  monitor API, warning-vs-station comparison, expert filters, minimal PWA shell,
  and planning docs for trends and OpenAPI client generation.
- Added Stage 10 product/radar research, frame-metadata API, map timeline
  endpoint, and frontend timeline shell with explicit metadata-only labels.
  Binary GRIB/radar parsing and map rendering remain deferred.
- Added Stage 9 geometry pipeline: local geometry manifest/cache, warning polygon
  map layers, spatial location matching, province/county/basin filters, and
  geometry dataset status API.
- Added Stage 8 observation history: SQLite persistence on IMGW refresh,
  time-series/compare/rankings API endpoints, range exports, retention policy,
  and frontend time-series chart mode.
- Added Stage 7 production deployment: `docker-compose.prod.yml`,
  production Dockerfiles, nginx static frontend, structured logging, IMGW
  retry/backoff settings, production CORS guidance, and public deployment
  checklist (`deploy/PRODUCTION_CHECKLIST.md`).
- Added documentation-only planning for Stages 7-11: public demo/production
  hardening, observation history and real time series, geometry datasets and
  spatial warnings, radar/product/GRIB research with timeline animation, and
  PWA/local-alert/dashboard power-user features.
- Added initial project research and documentation for Stages 0-1.
- Added Stage 2 application skeleton: FastAPI backend, React/Vite frontend,
  MapLibre map shell, Docker Compose, `.env.example`, CI, and basic tests.
- Added Stage 3 IMGW integration: HTTP client, source definitions, parser layer,
  normalized models, file cache, real-shape fixtures, and parser/cache tests.
- Added Stage 4 backend API endpoints for map layers, stations, warnings,
  location summaries, station CSV/JSON exports, and map GeoJSON exports backed
  by normalized cache records.
- Added Stage 4 backend tests for empty cache states, station/warning filters,
  missing geometry metadata, and export attribution.
- Documented IMGW-PIB source endpoints, archive entry points, fields, risks, and
  parser status.
- Documented architecture decisions for frontend, backend, cache, database,
  exports, and deployment.
- Documented attribution and processed-data requirements.
- Added Stage 5 frontend: map-first dashboard with layer registry/toggles,
  station markers, station/warning details panel with mobile bottom sheet,
  station search, "My location", ECharts station chart, CSV/JSON/GeoJSON/PNG
  exports, URL permalink state, keyboard shortcuts with help, light/dark/system
  theme, simple/expert mode, and loading/empty/stale/partial/error states.
- Added frontend dependency `echarts` and frontend unit tests for the app shell,
  state store, permalink serialization, formatting helpers, and API error
  parsing.
- Made Docker Compose host ports configurable via `BACKEND_PORT`/`FRONTEND_PORT`
  to avoid local port clashes; the frontend API base URL follows `BACKEND_PORT`.
- Addressed Stage 5 review feedback: filter warnings by current time (with a
  minute ticker), restore the permalink map view on first load, disable the map
  GeoJSON export when no layers are active, read API error codes from FastAPI
  `detail.error`, wire "My location" into a nearest-stations/warnings summary,
  keep the layer panel reachable on desktop, hydrate the saved theme before
  persisting, keep Docker CORS in sync with `FRONTEND_PORT`, embed attribution in
  PNG exports, surface non-empty cache errors instead of masking them, and render
  source timestamps in Polish (`Europe/Warsaw`) time.
- Added MVP roadmap and implementation task queue.
- Added Stage 6 quality work: backend parser/API edge-case tests (malformed
  payloads, bbox/date-range filters, cache-invalid handling) raising backend
  coverage to 99%; frontend component tests for `DetailsPanel`, `StationChart`,
  `ExportMenu`, `SearchBox`, `HeaderBar`, `ShortcutHelp`, `LocationSummary`,
  keyboard shortcuts, and the app store; a Playwright E2E suite
  (`frontend/e2e/`, wired into CI) seeded from the backend's own parser
  fixtures; explicit tests confirming attribution/processed-data notices
  appear in the UI, exports, and PNG captures; explicit tests confirming real
  zero values and missing values are never conflated; and a "Known
  Limitations" section in `README.md`.
- Added live IMGW startup cache refresh for Docker Compose so a fresh local
  run populates station and warning layers without a separate manual cache
  seeding step.
