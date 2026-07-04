# TASKS.md - MeteoLens Implementation Queue

## Stage 0 - Research

- [x] Verify IMGW-PIB API info page and current endpoint list.
- [x] Verify current `synop`, `hydro`, `meteo`, `warningsmeteo`,
  `warningshydro`, and `product` endpoints.
- [x] Verify archive directories for historical meteo/hydro warnings.
- [x] Verify measurement and observation archive entry points.
- [x] Document source fields, formats, risks, and parser status.
- [x] Document legal attribution requirements.

## Stage 1 - Documentation

- [x] Create `README.md`.
- [x] Create `AGENTS.md`.
- [x] Create `CLAUDE.md`.
- [x] Create `ARCHITECTURE.md`.
- [x] Create `DATA_SOURCES.md`.
- [x] Create `LEGAL_ATTRIBUTION.md`.
- [x] Create `ROADMAP.md`.
- [x] Create `TASKS.md`.
- [x] Create `API_CONTRACT.md`.
- [x] Create `UI_UX.md`.
- [x] Create `DEPLOYMENT.md`.
- [x] Create `TROUBLESHOOTING.md`.
- [x] Create `CHANGELOG.md`.
- [x] Create initial project directories.

## Stage 2 - Skeleton

- [x] Create `frontend/` with React, TypeScript, Vite.
- [x] Add Tailwind CSS and shadcn/ui-style utility setup.
- [x] Add MapLibre GL dependency and initial map shell.
- [x] Create `backend/` with FastAPI, Pydantic, httpx, pytest.
- [x] Add backend healthcheck endpoint.
- [x] Add Docker Compose.
- [x] Add `.env.example`.
- [x] Add lint/format/test commands.
- [x] Add basic CI workflow.

## Stage 3 - IMGW Integration

- [x] Add IMGW HTTP client with timeouts, retries, response metadata, and clear
  error reporting.
- [x] Add raw response cache model.
- [x] Add parser for `api/data/synop`.
- [x] Add parser for `api/data/hydro`.
- [x] Add parser for `api/data/meteo`.
- [x] Add parser for `api/data/warningsmeteo`.
- [x] Add parser for `api/data/warningshydro`.
- [x] Add product manifest parser for `api/data/product`.
- [x] Add normalization layer.
- [x] Add parser fixtures from real IMGW responses for tests.
- [x] Add tests for null handling, numeric conversion, and timestamps.

## Stage 4 - Backend API

- [x] Add `/health`.
- [x] Add `/api/v1/sources`.
- [x] Add `/api/v1/map/layers`.
- [x] Add `/api/v1/stations`.
- [x] Add `/api/v1/stations/{id}`.
- [x] Add `/api/v1/stations/{id}/observations`.
- [x] Add `/api/v1/warnings`.
- [x] Add `/api/v1/warnings/{id}`.
- [x] Add `/api/v1/location/summary`.
- [x] Add CSV/JSON/GeoJSON export endpoints.
- [x] Add backend tests for cache-backed API endpoints and exports.
- [x] Update `API_CONTRACT.md` after implementation.

## Stage 5 - Frontend

- [x] Add map shell centered on Poland.
- [x] Add layer registry and toggles.
- [x] Add legends.
- [x] Add station and warning markers/polygons. Stations render as coloured
  markers; warnings render as a filterable list because the backend exposes no
  area geometry yet (`missing_area_geometry_dataset`). Polygons land when TERYT
  and basin geometry datasets are cached.
- [x] Add details panel and mobile bottom sheet.
- [x] Add search.
- [x] Add "My location".
- [x] Add charts. Snapshot cache exposes one timestamp per station, so the chart
  shows current metric values; multi-frame time series follows archive data.
- [x] Add export controls (station CSV/JSON, map GeoJSON, current-map PNG).
- [x] Add permalink state.
- [x] Add keyboard shortcuts and shortcut help.
- [x] Add light/dark/system mode.
- [x] Add simple/expert mode.
- [x] Add loading, empty, stale, partial, and error states.

Deferred within Stage 5 scope: the bottom timeline/animation control is inert
until time-aware (archive/radar) data exists, and province/time-range quick
filters wait for area geometry and archive series.

## Stage 6 - Quality

- [x] Add backend parser/API test coverage.
- [x] Add frontend component tests.
- [x] Add basic E2E tests.
- [x] Verify attribution in UI and exports.
- [x] Verify missing values are not converted to zero.
- [x] Document known limitations before MVP release.
- [x] Wire live IMGW startup cache refresh for Docker Compose and add refresh
  tests.

## Stage 7 - Public Demo And Production Hardening

- [x] Add production deployment plan.
- [x] Add production Docker setup separate from dev Docker setup.
- [x] Replace the Vite dev server in production with a static frontend build
  served by nginx, Caddy, or an equivalent static server.
- [x] Keep the backend production image free of development-only dependencies.
- [x] Document reverse proxy and TLS setup.
- [x] Add production CORS configuration guidance.
- [x] Add restart policies and persistent volumes for small production
  deployments.
- [x] Add rate-limit, retry, and backoff guidance for IMGW access.
- [x] Add logging and monitoring requirements for source fetches, parser
  failures, stale cache, and API errors.
- [x] Add public deployment checklist.
- [x] Confirm the MIT License is documented in public deployment notes.
- [x] Verify current IMGW-PIB terms before public or commercial use.
- [x] Document populated-cache screenshot capture requirements for `README.md`.

## Stage 8 - Observation History And Real Time Series

- [x] Persist repeated observations instead of replacing each station with only
  the latest snapshot.
- [x] Design the SQLite observation-history schema with a migration path to
  PostgreSQL/PostGIS/TimescaleDB.
- [x] Add backend API contract for station time series.
- [x] Add time-series query parameters for metric, date/time range,
  aggregation interval, and limit.
- [x] Add time-series charts backed by real multi-point data.
- [x] Add station comparison.
- [x] Add rankings for highest temperature, lowest temperature, strongest wind,
  highest precipitation, and highest/lowest water level where applicable.
- [x] Add export support for selected time ranges.
- [x] Add retention policy for the local historical cache.
- [x] Preserve source timestamp, retrieval timestamp, data delay, attribution,
  missing values, and processed-data notice in historical views and exports.

## Stage 9 - Geometry Datasets And Spatial Warnings

- [x] Research legal/public TERYT administrative boundary datasets.
- [x] Research legal/public hydrological basin or catchment geometry datasets.
- [x] Research official station metadata or station coordinate lists for
  synoptic stations.
- [x] Add a source/legal review checklist for every external geometry dataset.
- [x] Design geometry import and cache pipeline.
- [x] Map meteorological warning TERYT codes to polygons.
- [x] Map hydrological warning basin or area codes to geometries where possible.
- [x] Reconcile synoptic station coordinates from an official or legally cleared
  station metadata source.
- [x] Add warning polygons on the map.
- [x] Add spatial matching for "My location" warnings.
- [x] Add province, county, and basin filters where geometry exists.
- [x] Clearly show missing geometry where mapping cannot be resolved.

## Stage 10 - Radar, Product Files, GRIB, And Timeline Animation

- [x] Research IMGW product API file types and identify high-value products.
- [x] Document product IDs that are stable, unstable, missing, or legally or
  technically risky.
- [x] Research radar-like products such as CAPPI, SRI, and MERGE if available
  from public sources.
- [x] Research GRIB/model files if available from public sources.
- [x] Defer binary parsing until formats, projection, licensing, file size, and
  cache strategy are documented.
- [x] Design raster/product ingestion pipeline.
- [x] Design tile generation or raster rendering strategy for MapLibre.
- [x] Add timeline and animation requirements for radar/product frames.
- [x] Add cache retention policy for large product files.
- [x] Add explicit UI labels for source time, frame time, missing frames, stale
  frames, and processed-data notice.

## Stage 11 - PWA, Local Alerts, Dashboards, And Power-User Features

- [x] Add PWA support planning.
- [x] Add saved locations.
- [x] Add saved map views.
- [x] Add user-defined dashboards.
- [x] Add local alert rules based on active warnings, thresholds, stale data,
  and nearby stations.
- [x] Add source availability dashboard.
- [x] Add data freshness monitor.
- [x] Add advanced expert filters.
- [x] Add warning-vs-measurement comparison.
- [x] Add trend and anomaly detection ideas.
- [x] Add generated public API client task from OpenAPI.
- [x] Keep alerting clearly separated from official warning responsibility;
  MeteoLens must not present itself as an official alerting system.

## Stage 12 - Public Alpha Release Polish

Goal: prepare the repository and app for an honest public alpha release.

Smoke-test record: `docs/release/SMOKE_TEST_2026-07-03.md`. The recorded run
used the supported `BACKEND_PORT`/`PUBLIC_HTTP_PORT` overrides because the
default host ports were taken locally.

- [x] Run and document a full local development smoke test with
  `docker compose up --build`.
- [x] Verify and record local smoke-test results for backend `/health`.
- [x] Verify and record local smoke-test results for backend `/api/v1/sources`.
- [x] Verify and record frontend map load against a populated live cache.
- [x] Verify and record station details behavior.
- [x] Verify and record warning details and warning list behavior.
- [x] Verify and record CSV, JSON, GeoJSON, and PNG exports.
- [x] Verify and record expert panel behavior.
- [x] Verify and record timeline shell behavior. With no cached product frame
  manifests the timeline stays hidden and `/api/v1/map/timeline` returns
  `layers: []`; that documented empty state is what the smoke script asserts.
- [x] Run and document a production smoke test using
  `cp deploy/.env.production.example .env.production` and
  `docker compose --env-file .env.production -f docker-compose.prod.yml up --build`.
  Required a small consistency fix: a root `.dockerignore` so the
  repository-root build context of `frontend/Dockerfile.prod` no longer trips
  over container-owned files in the `./data` bind mount.
- [x] Verify the configured public HTTP port opens during the production smoke
  test.
- [x] Capture populated-cache screenshots from real IMGW-backed data, not
  fixtures.
- [x] Add screenshots to `docs/screenshots/` and reference them from
  `README.md`.
- [x] Add a clear public-alpha status badge or section to `README.md`.
- [x] Add a short `v0.1.0-alpha` release checklist
  (`docs/release/RELEASE_CHECKLIST_v0.1.0-alpha.md`).
- [x] Fix documentation drift where `TASKS.md`, `README.md`, `CHANGELOG.md`, and
  `deploy/PRODUCTION_CHECKLIST.md` disagree.
- [x] Ensure screenshots visibly preserve IMGW-PIB attribution and
  processed-data notices.
- [x] Keep known limitations visible, including missing geometry, stale cache,
  and non-renderable product states.

Acceptance criteria:

- [x] A reviewer can reproduce the local and production smoke-test checks from
  documented commands (`docs/release/SMOKE_TEST_2026-07-03.md` plus
  `frontend/scripts/smoke.mjs`).
- [x] README screenshots show real IMGW-backed data and visible attribution.
- [x] `README.md`, `TASKS.md`, `CHANGELOG.md`, and
  `deploy/PRODUCTION_CHECKLIST.md` describe the same alpha readiness state.
  Tagging/publishing steps stay unchecked in the release checklist until the
  release is actually cut.

## Stage 13 - Reviewed Geometry Dataset MVP

Goal: make spatial warning features useful by adding a reviewed, reproducible
geometry dataset workflow.

Implemented: PRG © GUGiK voivodeship and county polygons are reviewed,
converted (`scripts/geometry/convert_prg_shapefiles.py`), validated, and
bundled under `data/geometry/`. Hydro basins (MPHP candidate) and the synop
coordinate dataset (WMO OSCAR candidate) stay `planned` pending terms review;
their backend mechanisms are implemented and tested with fixtures. Full review
notes: `docs/geometry/GEOMETRY_SOURCES.md`.

- [x] Select candidate public geometry sources for Polish province boundaries.
  Selected and implemented: PRG (GUGiK) via the GIS Support SHP mirror.
- [x] Select candidate public geometry sources for Polish county boundaries.
  Selected and implemented: PRG (GUGiK) via the GIS Support SHP mirror.
- [x] Select candidate public geometry sources for warning TERYT code matching.
  PRG `JPT_KOD_JE` attributes carry TERYT codes directly; live `warningsmeteo`
  codes resolved fully at import time.
- [x] Select candidate public hydrological basin or catchment geometries if
  legally usable. Candidate documented (MPHP, PGW Wody Polskie); **not**
  implemented — licensing and `kod_zlewni` mapping unverified.
- [x] Select a source for synoptic station coordinates from an official or
  legally cleared source. Candidate documented (WMO OSCAR/Surface; IMGW
  `wykaz_stacji.csv` has no coordinates); import pending terms review.
- [x] For every candidate dataset, document provider, canonical URL,
  license/terms URL, attribution text, public-use status, commercial-use status,
  caching/redistribution/screenshot/export implications, update cadence, and
  known limitations.
- [x] Add a reviewed dataset manifest format under `data/geometry/manifest.json`
  (format_version 2 with review metadata enforced by the loader).
- [x] Add an import/validation script or CLI for reviewed GeoJSON datasets
  (`python -m app.geometry.import_cli` plus reference metadata under
  `docs/geometry/metadata/`).
- [x] Validate GeoJSON syntax and expected geometry type before use.
- [x] Validate required dataset properties before use.
- [x] Validate TERYT, basin, or station identifier coverage before use.
- [x] Validate reasonable coordinate bounds for Poland before use.
- [x] Add backend tests for geometry manifest loading.
- [x] Add backend tests for invalid dataset rejection.
- [x] Add backend tests for TERYT-to-polygon mapping.
- [x] Add backend tests for unresolved geometry metadata.
- [x] Add backend tests for location-to-warning spatial matching.
- [x] Add frontend tests for warning polygon rendering when geometry exists.
- [x] Add frontend tests for fallback list-only state when geometry is missing.
- [x] Add frontend tests for province, county, and basin filters.
- [x] Update `docs/geometry/GEOMETRY_SOURCES.md`.
- [x] Update `DATA_SOURCES.md`.
- [x] Update `LEGAL_ATTRIBUTION.md`.
- [x] Update `README.md`.
- [x] Update `TASKS.md`.

Acceptance criteria:

- [x] The app can render at least one reviewed administrative geometry dataset
  on the warning layer (bundled PRG county/voivodeship polygons).
- [x] Missing or partial geometry remains explicit in API responses and UI
  (hydro basins and unresolved codes keep `geometry_not_found` /
  `missing_area_geometry_dataset`).
- [x] No unofficial or legally unclear geometry source is marked as implemented
  (MPHP and WMO OSCAR stay `planned`).
- [x] Synoptic stations only appear as map markers after coordinates come from a
  reviewed source (`coordinate_source` metadata; no reviewed dataset bundled
  yet, so synop stations stay off the map).

## Stage 14 - Radar/Product Rendering MVP

Goal: turn the current product metadata/timeline shell into the first real
rendered product layer on the map.

- [ ] Pick one technically realistic high-value product path first, such as a
  legally usable radar composite preview or a simple raster/tile pipeline for
  one stable product.
- [ ] Avoid full GRIB or radar binary decoding in one large step unless the
  format is fully documented.
- [ ] Add product-detail refresh support so selected product frame manifests can
  be refreshed automatically with retention limits.
- [ ] Add cache limits for product detail manifests and downloaded renderable
  files.
- [ ] Add explicit source time, frame time, retrieval time, stale status,
  missing frame status, rendering status, attribution, and processed-data notice
  metadata.
- [ ] Add backend API support for a renderable map layer descriptor only when
  frames are actually renderable.
- [ ] Add frontend support for selecting a renderable product layer.
- [ ] Add frontend support for displaying frame time.
- [ ] Add frontend support for play, pause, and step controls across frames.
- [ ] Add frontend labels for metadata-only or not-renderable frames when map
  rendering is unavailable.
- [ ] Add tests for frame metadata parsing.
- [ ] Add tests for retention policy.
- [ ] Add tests for missing frame handling.
- [ ] Add tests for stale frame handling.
- [ ] Add tests for frontend timeline state.
- [ ] Update `docs/products/PRODUCT_RESEARCH.md`.
- [ ] Update `docs/products/RASTER_PIPELINE.md`.
- [ ] Update `API_CONTRACT.md`.
- [ ] Update `DATA_SOURCES.md`.
- [ ] Update `README.md`.
- [ ] Update `TASKS.md`.

Acceptance criteria:

- [ ] At least one product path can be represented as a real map-renderable
  layer, or the docs clearly explain why the stage remains blocked by format or
  legal constraints.
- [ ] The UI never presents metadata-only frames as rendered radar or model data.
- [ ] All rendered or exported product views include IMGW-PIB attribution and a
  processed-data notice.

## Stage 15 - Historical Archive Backfill

Goal: add optional historical backfill so station charts and rankings do not
depend only on data collected after this deployment starts.

- [ ] Research current IMGW public archive formats for synop observations.
- [ ] Research current IMGW public archive formats for hydro observations.
- [ ] Research current IMGW public archive formats for meteo observations.
- [ ] Document archive endpoints or directories, file formats, update cadence,
  and legal notes.
- [ ] Design an opt-in, bounded-time-range backfill process.
- [ ] Ensure the backfill process is rate-limited and resumable.
- [ ] Add clear progress and error reporting for backfill runs.
- [ ] Keep archive fetching server-side; do not add direct browser-to-IMGW
  archive calls.
- [ ] Add backend import logic for at least one archive source if legally and
  technically clear.
- [ ] Normalize archive records into the existing observation-history schema.
- [ ] Preserve source timestamp, retrieval/import timestamp, source attribution,
  processed-data notice, and missing/null values.
- [ ] Add API metadata distinguishing live refresh history, imported archive
  history, and mixed series.
- [ ] Add frontend labels for imported historical data.
- [ ] Add tests for parser correctness.
- [ ] Add tests for duplicate handling.
- [ ] Add tests for null handling.
- [ ] Add tests for time-range queries.
- [ ] Add tests for retention interaction.
- [ ] Add tests for mixed live/archive series.
- [ ] Update `DATA_SOURCES.md`.
- [ ] Update `API_CONTRACT.md`.
- [ ] Update `README.md`.
- [ ] Update `TASKS.md`.
- [ ] Update `TROUBLESHOOTING.md`.

Acceptance criteria:

- [ ] A fresh deployment can optionally import a bounded historical time range
  for at least one supported source.
- [ ] Charts can show multi-point historical data immediately after a successful
  backfill.
- [ ] Imported data is clearly labelled as processed IMGW-PIB data.

## Stage 16 - Public API, SDK, And Power-User Exports

Goal: make MeteoLens easier to integrate, automate, and use as a data
exploration tool.

- [ ] Stabilize and document the public API surface.
- [ ] Generate or prepare a TypeScript API client from OpenAPI.
- [ ] Add example scripts for listing stations.
- [ ] Add example scripts for fetching station observations.
- [ ] Add example scripts for exporting station time ranges.
- [ ] Add example scripts for checking source freshness.
- [ ] Add example scripts for getting active warnings for a location.
- [ ] Add stronger station time-range CSV export support.
- [ ] Add stronger station time-range JSON export support.
- [ ] Add warning GeoJSON export support.
- [ ] Add map state JSON export support.
- [ ] Plan optional report-like PDF export without presenting it as implemented.
- [ ] Add API versioning notes and a backwards-compatibility policy.
- [ ] Add rate-limit and responsible-use notes for deployed instances.
- [ ] Add tests for generated or exported API examples where practical.
- [ ] Update `API_CONTRACT.md`.
- [ ] Update `README.md`.
- [ ] Update `ROADMAP.md`.
- [ ] Update `TASKS.md`.
- [ ] Update `CHANGELOG.md`.

Acceptance criteria:

- [ ] A developer can understand the supported API without reading backend code.
- [ ] Exported files include attribution and processed-data notices.
- [ ] The frontend and generated client do not drift from the backend API
  contract.
