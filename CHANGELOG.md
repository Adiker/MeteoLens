# CHANGELOG

All notable changes to MeteoLens will be documented in this file.

## Unreleased

- Added Stage 22 reviewed hydro basin geometry: bundled II aPGW JCWP catchment
  polygons (CC BY 4.0, PGW Wody Polskie) mapped to IMGW `kod_zlewni`, dissolved
  and simplified via `scripts/geometry/convert_apgw_hydro_basins.py`, imported
  through the geometry CLI with coverage report
  `docs/geometry/hydro_basins.coverage.json` (**297/297** snapshot codes
  resolved into 170 features via MPHP-core matching, name/voivodeship
  refinement, and curated coastal CW/TW rules; `mapping_precision`
  standard/refined/coarse/coastal). Loader resolves `kod_zlewni_codes` aliases;
  spatial status distinguishes loaded-but-unmatched codes from a missing
  dataset. Warning detail, map layers, and GeoJSON exports now thread
  `mapping_precision` / `mapping_method` onto resolved basin areas; the details
  panel flags non-`standard` precision as an IMGW forecasting-area approximation.

## 0.1.0-alpha - 2026-07-20

- Published the first public alpha: tagged `v0.1.0-alpha`, moved these notes out
  of `Unreleased`, and created the GitHub prerelease with release notes,
  screenshots, attribution, license, and known limitations.
- Recorded the final automated pre-tag suite for the release base commit in
  `docs/release/STAGE_21_PRETAG_2026-07-20.md` (249 backend tests, 87 frontend
  unit tests, 5 E2E tests, lint, and production build).
- Documented repository governance for branch cleanup, commits, pull requests,
  and merge strategy while preserving the existing `main` history.
- Completed Stage 21 current-main validation
  (`docs/release/STAGE_21_VALIDATION_2026-07-14.md`): repeatable live
  development and nginx production smoke tests, fresh-volume and pre-Stage-18
  upgrade checks, COSMO render/cache checks, source-outage, bounded archive,
  abuse-limit, backup/restore checks, refreshed screenshots, and rollback
  guidance.
- Added reviewed SYNOP live/archive station-ID reconciliation: a versioned map
  from official IMGW `wykaz_stacji.csv` codes to current `id_stacji`, bounded
  archive imports that retain unmapped `synop-archive:<NSP>` records, and a
  live follow-up proving `series_origin=mixed` for a mapped station.
- Hardened product rendering and archive imports: validate product download URLs
  before cache lookup and server-side fetch, and cap SYNOP archive ZIP resource
  usage with clearer invalid-archive handling.
- Fixed station details so normalized meteo metric names are shown in Polish
  and the measurement list displays only the current snapshot instead of
  flattening historical points into apparent duplicate rows; charts continue
  to use the full observation history.
- Added Stage 20 production observability, backup, and recovery: explicit
  liveness/readiness semantics, internal Prometheus metrics/alerts, JSON
  request-correlated logs, Compose resource/log limits, deterministic SQLite
  backup/restore tooling, a fresh-volume restore record, and operational
  runbooks.
- Aligned GitHub Actions maintenance with `keyboard-volume-app`: fixed
  `ubuntu-24.04` runners, current commit-pinned actions, daily Actions
  Dependabot updates, lockfile-driven `uv` backend CI, and separately guarded
  Claude automatic-review/verifier workflow scaffolds adapted to MeteoLens.
- Added Stage 19 public-internet security and abuse protection: public,
  expensive, and administrative route classification; fail-closed admin-token
  archive backfill; rate/concurrency/duplicate-work controls; nginx request and
  header safeguards; non-root read-only production containers; restricted,
  commit-pinned AI workflows; dependency/secret/container scanning; safe-log
  redaction; `SECURITY.md`; and focused regression tests/documentation.
- Fixed Stage 19 review findings: production CSP now permits OSM basemap tiles,
  geometry upgrades safely reuse UID-10001-owned volumes, Caddy keeps nginx as
  the single application entrypoint with trusted proxy addresses, and custom
  API errors preserve authentication and cooldown headers.
- Added documentation-only planning for Stages 19-26: public-internet security
  and abuse protection, production observability/backup/recovery,
  current-main `v0.1.0-alpha` validation, hydro basin geometry, hydrological
  archive backfill, warning history, performance/scalability hardening, and
  PDF reports. The plan renumbers the old unimplemented candidate items and
  originally kept all Stage 19-26 work explicitly planned; Stage 19 is now
  implemented by the hardening work above.
- Added Stage 18 reviewed synop station coordinates: bundled a reviewed WMO
  OSCAR/Surface `synop_stations` Point dataset for all 62 current IMGW SYNOP
  station IDs, added a reproducible fetch/import pipeline, documented
  WMO/OSCAR source/legal review and attribution, and updated docs so synop
  stations are no longer described as map-marker blocked.
- Added Stage 17 post-Stage-16 stabilization: aligned documentation/status notes
  after Stage 16, corrected stale future-tense references in agent,
  architecture, API, and UI docs, recorded the then-next stage candidates, and
  kept the pass documentation-only with no runtime/API/source changes.
- Added Stage 16 public API, SDK, and power-user exports: stabilized
  `API_CONTRACT.md` with `/api/v1` compatibility and responsible-use notes,
  added warning GeoJSON and map-state JSON export endpoints, exposed those
  exports in the frontend menu, added a lightweight TypeScript client with
  OpenAPI-generated metadata under `packages/meteolens-api-client/`, added
  runnable Node API examples under `examples/api/`, documented the generator
  workflow, and added tests for Stage 16 exports, generated metadata, and
  example script syntax.
- Added Stage 15 historical archive backfill: bounded server-side daily SYNOP
  archive import (`POST /api/v1/archive/backfill/synop-daily`) with date/file
  limits, per-file rate limiting, resumable upserts, import-run progress/error
  reporting, origin metadata for live/archive/mixed series, frontend labels for
  imported history, and backend tests for parser correctness, duplicates,
  null/status handling, time ranges, retention, and mixed series.
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
  At that point binary GRIB/radar parsing and map rendering remained deferred;
  Stage 14 later added the reviewed COSMO rendering path while radar stayed
  blocked at the source.
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
