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
bundled under `data/geometry/`. Hydro basins (MPHP candidate) stay `planned`
until their own terms and mapping review is complete. The synop coordinate
mechanism was implemented and tested with fixtures in Stage 13, then the
reviewed WMO OSCAR/Surface dataset was bundled in Stage 18. Full review notes:
`docs/geometry/GEOMETRY_SOURCES.md`.

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
  `wykaz_stacji.csv` has no coordinates); imported after Stage 18 terms review.
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
  (MPHP stays `planned`; WMO OSCAR/Surface was promoted to implemented only
  after Stage 18 source/legal review).
- [x] Synoptic stations only appear as map markers after coordinates come from a
  reviewed source (`coordinate_source` metadata; Stage 18 now bundles the
  reviewed WMO OSCAR/Surface dataset).

## Stage 14 - Radar/Product Rendering MVP

Goal: turn the current product metadata/timeline shell into the first real
rendered product layer on the map.

- [x] Pick one technically realistic high-value product path first, such as a
  legally usable radar composite preview or a simple raster/tile pipeline for
  one stable product. (Chosen: COSMO `*_00` GRIB1 2 m temperature — format and
  grid documented by the product readme and verified live on 2026-07-05. Radar
  composites are blocked at the source: every public file URL 307-redirects to
  an HTML page; documented in `docs/products/PRODUCT_RESEARCH.md`.)
- [x] Avoid full GRIB or radar binary decoding in one large step unless the
  format is fully documented. (Narrow GRIB1 reader: simple packing plus
  rotated lat/lon GDS only; a single variable is decoded per render.)
- [x] Add product-detail refresh support so selected product frame manifests can
  be refreshed automatically with retention limits
  (`METEOLENS_PRODUCT_REFRESH_ENABLED`, `METEOLENS_PRODUCT_REFRESH_IDS`,
  startup sync + scheduler loop).
- [x] Add cache limits for product detail manifests and downloaded renderable
  files (`METEOLENS_PRODUCT_MAX_DETAIL_MANIFESTS`,
  `METEOLENS_PRODUCT_BINARY_MAX_FILES`, `METEOLENS_PRODUCT_MAX_CACHED_FILES`,
  age-based eviction via `METEOLENS_PRODUCT_FILE_RETENTION_HOURS`).
- [x] Add explicit source time, frame time, retrieval time, stale status,
  missing frame status, rendering status, attribution, and processed-data notice
  metadata (frames API, render metadata sidecars, PNG iTXt chunks, response
  headers).
- [x] Add backend API support for a renderable map layer descriptor only when
  frames are actually renderable (`renderable` block on timeline layers and
  the frames endpoint; metadata-only products keep `renderable: null`).
- [x] Add frontend support for selecting a renderable product layer (timeline
  layer picker plus an explicit "Pokaż na mapie" overlay opt-in).
- [x] Add frontend support for displaying frame time (frame time plus model
  run time).
- [x] Add frontend support for play, pause, and step controls across frames.
- [x] Add frontend labels for metadata-only or not-renderable frames when map
  rendering is unavailable (per-frame render window/step reasons, blocked
  radar downloads, overlay load errors).
- [x] Add tests for frame metadata parsing.
- [x] Add tests for retention policy.
- [x] Add tests for missing frame handling.
- [x] Add tests for stale frame handling.
- [x] Add tests for frontend timeline state.
- [x] Update `docs/products/PRODUCT_RESEARCH.md`.
- [x] Update `docs/products/RASTER_PIPELINE.md`.
- [x] Update `API_CONTRACT.md`.
- [x] Update `DATA_SOURCES.md`.
- [x] Update `README.md`.
- [x] Update `TASKS.md`.

Acceptance criteria:

- [x] At least one product path can be represented as a real map-renderable
  layer, or the docs clearly explain why the stage remains blocked by format or
  legal constraints. (COSMO 2 m temperature renders as a MapLibre image
  overlay; the radar path is documented as blocked at the source.)
- [x] The UI never presents metadata-only frames as rendered radar or model data.
- [x] All rendered or exported product views include IMGW-PIB attribution and a
  processed-data notice (timeline bar, layer descriptor, PNG iTXt metadata).

## Stage 15 - Historical Archive Backfill

Goal: add optional historical backfill so station charts and rankings do not
depend only on data collected after this deployment starts.

- [x] Research current IMGW public archive formats for synop observations.
- [x] Research current IMGW public archive formats for hydro observations.
- [x] Research current IMGW public archive formats for meteo observations.
- [x] Document archive endpoints or directories, file formats, update cadence,
  and legal notes.
- [x] Design an opt-in, bounded-time-range backfill process.
- [x] Ensure the backfill process is rate-limited and resumable.
- [x] Add clear progress and error reporting for backfill runs.
- [x] Keep archive fetching server-side; do not add direct browser-to-IMGW
  archive calls.
- [x] Add backend import logic for at least one archive source if legally and
  technically clear.
- [x] Normalize archive records into the existing observation-history schema.
- [x] Preserve source timestamp, retrieval/import timestamp, source attribution,
  processed-data notice, and missing/null values.
- [x] Add API metadata distinguishing live refresh history, imported archive
  history, and mixed series.
- [x] Add frontend labels for imported historical data.
- [x] Add tests for parser correctness.
- [x] Add tests for duplicate handling.
- [x] Add tests for null handling.
- [x] Add tests for time-range queries.
- [x] Add tests for retention interaction.
- [x] Add tests for mixed live/archive series.
- [x] Update `DATA_SOURCES.md`.
- [x] Update `API_CONTRACT.md`.
- [x] Update `README.md`.
- [x] Update `TASKS.md`.
- [x] Update `TROUBLESHOOTING.md`.

Acceptance criteria:

- [x] A fresh deployment can optionally import a bounded historical time range
  for at least one supported source.
- [x] Charts can show multi-point historical data immediately after a successful
  backfill.
- [x] Imported data is clearly labelled as processed IMGW-PIB data.

Stage 15 implementation note: daily SYNOP archives are implemented first through
`POST /api/v1/archive/backfill/synop-daily`. Hydrological archives and broader
meteorological archive families are researched and documented, but remain
planned parser/importer work.

## Stage 16 - Public API, SDK, And Power-User Exports

Goal: make MeteoLens easier to integrate, automate, and use as a data
exploration tool.

- [x] Stabilize and document the public API surface.
- [x] Generate or prepare a TypeScript API client from OpenAPI.
- [x] Add example scripts for listing stations.
- [x] Add example scripts for fetching station observations.
- [x] Add example scripts for exporting station time ranges.
- [x] Add example scripts for checking source freshness.
- [x] Add example scripts for getting active warnings for a location.
- [x] Add stronger station time-range CSV export support.
- [x] Add stronger station time-range JSON export support.
- [x] Add warning GeoJSON export support.
- [x] Add map state JSON export support.
- [x] Plan optional report-like PDF export without presenting it as implemented.
- [x] Add API versioning notes and a backwards-compatibility policy.
- [x] Add rate-limit and responsible-use notes for deployed instances.
- [x] Add tests for generated or exported API examples where practical.
- [x] Update `API_CONTRACT.md`.
- [x] Update `README.md`.
- [x] Update `ROADMAP.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.

Acceptance criteria:

- [x] A developer can understand the supported API without reading backend code.
- [x] Exported files include attribution and processed-data notices.
- [x] The frontend and generated client do not drift from the backend API
  contract.

Stage 16 implementation note: `API_CONTRACT.md` now documents the supported
`/api/v1` surface, compatibility policy, and responsible-use/rate-limit
guidance. `packages/meteolens-api-client/` contains a lightweight TypeScript
client with OpenAPI-generated metadata from
`scripts/api/generate_ts_client.py`. Runnable Node examples live under
`examples/api/`. New exports include `GET /api/v1/export/warnings.geojson` and
`GET /api/v1/export/map-state.json`; station observation range CSV/JSON exports
remain the supported time-range export path. PDF reports remain planned only in
`docs/power-user/PDF_EXPORT_PLAN.md`.

## Stage 17 - Post-Stage-16 Stabilization

Goal: align documentation and release/status notes after Stage 16 without
changing runtime behavior, public API shape, schemas, source integrations, or
tests.

- [x] Confirm repository status and current branch before documentation edits.
- [x] Verify Stage 14-16 are consistently treated as implemented where code,
  tests, and docs exist.
- [x] Update `CLAUDE.md` so it no longer carries the old Stage 14-16 status.
- [x] Correct stale future-tense implementation notes in `ARCHITECTURE.md`.
- [x] Correct stale Stage 8/10 future-tense notes in `API_CONTRACT.md`.
- [x] Correct stale future-tense UX notes in `UI_UX.md` and keep future UX
  candidates separate from implemented behavior.
- [x] Update `ROADMAP.md` with Stage 17 and the then-planned next-stage
  candidates.
- [x] Update `CHANGELOG.md` with Stage 17 documentation/status cleanup.
- [x] Keep `README.md`, `DATA_SOURCES.md`, and `LEGAL_ATTRIBUTION.md` unchanged
  because they already describe the Stage 16 state and source/legal constraints
  consistently.
- [x] Do not add sources, change API/runtime behavior, or mark `hydro_basins`,
  `synop_stations`, PDF reports, or radar rendering as implemented.
- [x] Run backend lint/tests and frontend lint/tests/build.

Acceptance criteria:

- [x] Documentation no longer contains contradictory Stage 14-16 status notes.
- [x] `TASKS.md`, `README.md`, `ROADMAP.md`, `CHANGELOG.md`, and `CLAUDE.md`
  describe the same Stage 0-17 project state.
- [x] Stage 17 is clearly documentation/status stabilization only.
- [x] Future-stage items were listed as candidates, not implemented features.

## Stage 18 - Reviewed Synop Station Coordinates

Goal: render synoptic stations on the map only after importing reviewed station
coordinates from a legally documented source.

- [x] Review WMO OSCAR/Surface as the station-coordinate source for current
  IMGW SYNOP station IDs.
- [x] Verify public OSCAR/Surface station metadata can be fetched by WIGOS ID
  (`0-20000-0-<id_stacji>`).
- [x] Add a reproducible generator
  (`scripts/geometry/fetch_oscar_synop_stations.py`) that discovers current
  IMGW SYNOP IDs and resolves them through OSCAR/Surface.
- [x] Add reviewed metadata under `docs/geometry/metadata/synop_stations.json`.
- [x] Generate and import `data/geometry/synop_stations.geojson` through
  `python -m app.geometry.import_cli`.
- [x] Preserve WMO OSCAR/Surface attribution and IMGW-PIB measurement-source
  attribution in dataset metadata.
- [x] Keep commercial-use clearance conservative; public use is reviewed, but
  commercial deployments must re-review WMO/OSCAR terms.
- [x] Verify all current IMGW SYNOP station IDs resolve to reviewed coordinates
  during the Stage 18 import.
- [x] Add or update tests for the bundled production `synop_stations` dataset.
- [x] Update `README.md`.
- [x] Update `ARCHITECTURE.md`.
- [x] Update `API_CONTRACT.md`.
- [x] Update `DATA_SOURCES.md`.
- [x] Update `LEGAL_ATTRIBUTION.md`.
- [x] Update `docs/geometry/GEOMETRY_SOURCES.md`.
- [x] Update `UI_UX.md`.
- [x] Update `ROADMAP.md`.
- [x] Update `TASKS.md`.
- [x] Update `CHANGELOG.md`.

Acceptance criteria:

- [x] A fresh checkout includes a reviewed `synop_stations` dataset under
  `data/geometry/` and loads it through the existing geometry manifest.
- [x] Synop stations render as map markers when current IMGW cache data is
  present, with visible `coordinate_source` metadata.
- [x] Future unresolved station IDs remain explicit as `missing_lat_lon`.
- [x] No source/legal ambiguity is hidden; commercial deployments are told to
  re-review WMO/OSCAR terms.

## Stage 19 - Public Internet Security And Abuse Protection

Goal: make an internet-exposed MeteoLens instance resistant to trivial abuse and
reduce the security impact of compromised or malformed requests.

Implementation tasks:

- [ ] Classify API routes as public, expensive, or administrative.
- [ ] Protect or disable the archive-backfill endpoint by default in public
  deployments.
- [ ] Define and implement an admin authentication mechanism for administrative
  operations.
- [ ] Add request and per-IP rate limiting at the proxy or backend boundary.
- [ ] Add lower limits for expensive product-render requests.
- [ ] Limit concurrent downloads, renders, and archive imports.
- [ ] Define queueing, cache-only serving, pre-rendering, or another safe
  execution model for large COSMO frames.
- [ ] Prevent repeated public requests from forcing unnecessary approximately
  160 MB downloads or CPU-heavy renders.
- [ ] Add nginx request, connection, timeout, and response-size safeguards.
- [ ] Review CORS behavior for same-origin production and diagnostic access.
- [ ] Add recommended HTTP security headers.
- [ ] Run the backend production container as a non-root user.
- [ ] Drop unnecessary Linux capabilities in production Compose.
- [ ] Enable `no-new-privileges` for production containers.
- [ ] Evaluate a read-only root filesystem while preserving writable `/data`.
- [ ] Restrict Claude and OpenCode workflows to trusted actors or repository
  collaborators.
- [ ] Prevent arbitrary public comments from consuming paid AI workflow
  credentials.
- [ ] Pin third-party GitHub Actions to stable versions or commit SHAs.
- [ ] Add dependency, secret, and container scanning.
- [ ] Add or plan a `SECURITY.md` vulnerability-reporting policy.
- [ ] Ensure logs do not expose secrets or unnecessary sensitive location data.

Documentation tasks:

- [ ] Document public, expensive, and administrative endpoint categories.
- [ ] Document geolocation and request-log privacy expectations.
- [ ] Update `API_CONTRACT.md` with public-use and admin-operation guidance.
- [ ] Update `DEPLOYMENT.md` and `deploy/PRODUCTION_CHECKLIST.md` with the
  selected hardening controls.
- [ ] Update workflow documentation with trusted-actor restrictions.
- [ ] Keep security limitations explicit.

Test tasks:

- [ ] Add backend tests for admin-only archive imports.
- [ ] Add backend or proxy tests for rate limits and render concurrency limits.
- [ ] Add tests proving expensive rendering cannot be trivially multiplied.
- [ ] Add nginx configuration tests or smoke checks for request, timeout,
  response-size, and security-header behavior.
- [ ] Add workflow tests or documented dry-runs for trusted-actor gating.
- [ ] Add deployment checks confirming the backend container does not run as
  root and uses the intended capability restrictions.

Non-goals and blocked items:

- [ ] Do not add new public data products in this stage.
- [ ] Do not turn MeteoLens into an official warning service.
- [ ] Do not design a Kubernetes-only security model; keep Docker Compose as
  the reference deployment.

Acceptance criteria:

- [ ] Unauthenticated users cannot trigger administrative archive imports.
- [ ] Expensive product rendering is bounded and cannot be trivially multiplied.
- [ ] Public users cannot trigger credential-backed AI workflows unless
  explicitly allowed.
- [ ] The backend production container does not run as root.
- [ ] Production HTTP safeguards are documented and testable.
- [ ] Security limitations remain explicit.

## Stage 20 - Production Observability, Backup And Recovery

Goal: make a public deployment diagnosable and recoverable.

Implementation tasks:

- [ ] Separate liveness and readiness semantics.
- [ ] Monitor IMGW source freshness and parser failures.
- [ ] Monitor refresh durations and failures.
- [ ] Monitor product downloads, render duration, queue state, and cache hits.
- [ ] Monitor archive imports and failures.
- [ ] Monitor SQLite size, cache size, product-cache size, disk usage, memory,
  and CPU.
- [ ] Add structured and rotation-safe logs.
- [ ] Add correlation or request identifiers where useful.
- [ ] Add container resource limits suitable for a small self-hosted deployment.
- [ ] Define operational thresholds and alert recommendations.
- [ ] Improve graceful degradation when IMGW sources are unavailable.
- [ ] Define `/data` backup scope for database, cache metadata, reviewed
  geometry, product manifests, rendered products, and local history.
- [ ] Define restore commands and validation checks.
- [ ] Verify restore from backup on a fresh volume.
- [ ] Document persistent-volume upgrade and rollback guidance.
- [ ] Write an incident-response and troubleshooting runbook.
- [ ] Document what can be recreated from IMGW and what must be backed up.

Documentation tasks:

- [ ] Update `DEPLOYMENT.md` with monitoring, thresholds, resource budgets, and
  backup/restore procedures.
- [ ] Update `deploy/PRODUCTION_CHECKLIST.md` with observability, backup,
  restore-test, and incident-response gates.
- [ ] Update `TROUBLESHOOTING.md` with public-deployment failure modes.
- [ ] Record a restore-test result in `docs/release/` or another release note.

Test tasks:

- [ ] Add health/readiness tests.
- [ ] Add tests for degraded source and stale-cache reporting.
- [ ] Add tests or smoke checks for backup and restore commands.
- [ ] Add resource-exhaustion or cache-size smoke checks where practical.
- [ ] Add log-shape tests for source failures, render failures, and archive
  import failures.

Non-goals and blocked items:

- [ ] Do not require managed cloud services for the reference deployment.
- [ ] Do not add alert delivery that could be confused with official IMGW-PIB
  warnings.

Acceptance criteria:

- [ ] An operator can identify stale or failed sources without reading raw
  container output.
- [ ] Disk and resource exhaustion risks are visible.
- [ ] `/data` can be backed up and restored through documented commands.
- [ ] A restore test is recorded.
- [ ] Public deployment failure modes and recovery actions are documented.

## Stage 21 - Current-Main Production Validation And v0.1.0-alpha Release

Goal: validate the current Stage 0-20 application and publish the first honest
prerelease.

Implementation tasks:

- [ ] Rerun development smoke tests against the current `main` release commit.
- [ ] Rerun production smoke tests against the current `main` release commit.
- [ ] Record exact commit SHA, date, Docker version, Compose version, and test
  environment.
- [ ] Test a fresh named volume.
- [ ] Test an upgrade from an existing pre-Stage-18 volume.
- [ ] Verify bundled PRG geometry.
- [ ] Verify bundled SYNOP station coordinates.
- [ ] Verify SYNOP markers and `coordinate_source`.
- [ ] Verify meteorological warning polygons.
- [ ] Verify explicit missing hydro basin geometry.
- [ ] Verify one real COSMO temperature frame render.
- [ ] Verify cached replay of the rendered frame.
- [ ] Verify render failure and source-unavailable states.
- [ ] Verify a bounded archive backfill.
- [ ] Verify live/archive/mixed observation series.
- [ ] Verify exports and attribution.
- [ ] Verify source outage behavior.
- [ ] Test backup and restore.
- [ ] Run a small abuse/load smoke test for expensive routes.
- [ ] Update screenshots to match the current implementation.
- [ ] Update release notes.
- [ ] Move relevant `CHANGELOG.md` entries from `Unreleased` to a dated
  `0.1.0-alpha` section.
- [ ] Align backend, frontend, README, and release version metadata.
- [ ] Define rollback steps.
- [ ] Tag `v0.1.0-alpha`.
- [ ] Create a GitHub prerelease.
- [ ] Verify rendered release notes, screenshots, links, license, attribution,
  and known limitations.

Documentation tasks:

- [ ] Update `docs/release/RELEASE_CHECKLIST_v0.1.0-alpha.md` as checks pass.
- [ ] Record the current-main smoke-test run in `docs/release/`.
- [ ] Update `README.md` screenshots and alpha status if the release is cut.
- [ ] Update `CHANGELOG.md` only when the release is actually performed.
- [ ] Keep known limitations prominently visible.

Test tasks:

- [ ] Run backend tests and lint.
- [ ] Run frontend tests, lint, and build.
- [ ] Run E2E tests.
- [ ] Run production smoke tests against nginx and runtime images.
- [ ] Run fresh-volume and upgrade-path smoke tests.
- [ ] Run backup/restore verification.
- [ ] Run a small abuse/load smoke test for archive and product-render routes.

Non-goals and blocked items:

- [ ] Do not tag or publish the release until Stages 19-20 acceptance criteria
  are met.
- [ ] Do not promote the release beyond alpha.
- [ ] Do not claim legal certainty for deployers who must re-review source
  terms.

Acceptance criteria:

- [ ] A production smoke-test record exists for the current release commit.
- [ ] Both fresh install and persistent-volume upgrade paths pass.
- [ ] Stage 13-20 behavior is covered.
- [ ] The release checklist has no unresolved release-blocking items.
- [ ] The release remains clearly labelled as alpha.
- [ ] Known limitations are prominently visible.

## Stage 22 - Hydro Basin Geometry MVP

Goal: add hydrological warning polygons only after a reviewed and reproducible
basin-geometry source is available.

Implementation tasks:

- [ ] Perform legal and source review of MPHP or an alternative official
  hydrological basin dataset.
- [ ] Analyze public-use, commercial-use, redistribution, caching, screenshot,
  and export implications.
- [ ] Build a reproducible import pipeline for the selected basin dataset.
- [ ] Validate geometry type, coordinate bounds, simplification, and required
  properties.
- [ ] Map IMGW `kod_zlewni` values to geometry identifiers.
- [ ] Analyze coverage using real warning payloads.
- [ ] Render hydrological warning polygons when codes resolve.
- [ ] Add location matching against hydrological warning polygons.
- [ ] Add basin filters backed by reviewed geometry.
- [ ] Add dataset versioning and an update procedure.
- [ ] Preserve attribution and processed-data notices.
- [ ] Expose unresolved-code metadata for unmapped or ambiguous basin codes.

Documentation tasks:

- [ ] Update `docs/geometry/GEOMETRY_SOURCES.md`.
- [ ] Update `DATA_SOURCES.md`.
- [ ] Update `LEGAL_ATTRIBUTION.md`.
- [ ] Update `API_CONTRACT.md`.
- [ ] Update `UI_UX.md`.
- [ ] Update `README.md` known limitations after implementation.
- [ ] Update `TASKS.md` only as work is completed.

Test tasks:

- [ ] Add backend import and validation tests.
- [ ] Add backend warning-code coverage tests with realistic fixtures.
- [ ] Add API tests for hydro polygons and unresolved metadata.
- [ ] Add frontend tests for hydro polygon rendering, basin filters, and
  list-only fallback.
- [ ] Add export tests for basin geometry attribution and missing geometry.
- [ ] Add upgrade tests for bundled or imported basin datasets.

Non-goals and blocked items:

- [ ] Do not describe hydro basin polygons as implemented until the dataset
  review, import, API, UI, docs, and tests land.
- [ ] Do not add legally unclear basin geometry.
- [ ] Do not hide warnings whose basin codes remain unresolved.

Acceptance criteria:

- [ ] Hydrological warning polygons render only from reviewed geometry.
- [ ] `kod_zlewni` coverage and unresolved codes are documented and exposed.
- [ ] Location matching includes hydro polygons where available.
- [ ] Exports include correct basin attribution and processed-data notices.
- [ ] Hydro warning gaps remain visible.

## Stage 23 - Hydrological Archive Backfill

Goal: extend bounded historical imports beyond daily SYNOP.

Implementation tasks:

- [ ] Research hydro archive files, directory layout, formats, encodings, and
  update cadence.
- [ ] Document parsing status and quality/status fields.
- [ ] Handle nulls, sentinel values, measurement status, corrections,
  duplicates, and station-ID changes.
- [ ] Add bounded and resumable hydro archive imports.
- [ ] Add progress reporting for hydro import runs.
- [ ] Apply admin protection and rate limits from Stage 19.
- [ ] Define database retention interaction for hydro history.
- [ ] Preserve live/archive/mixed-series behavior.
- [ ] Add hydro charts, rankings, comparisons, and exports where data quality
  supports them.
- [ ] Preserve attribution, source URLs, import timestamps, and processed-data
  notices.

Documentation tasks:

- [ ] Update `DATA_SOURCES.md` with verified hydro archive formats only.
- [ ] Update `API_CONTRACT.md` with supported import kinds and series metadata.
- [ ] Update `LEGAL_ATTRIBUTION.md` if source terms or attribution differ.
- [ ] Update `README.md` and `TROUBLESHOOTING.md`.
- [ ] Update `TASKS.md` only as work is completed.

Test tasks:

- [ ] Add parser tests using realistic hydro archive fixtures.
- [ ] Add duplicate, null, sentinel, correction, and station-ID-change tests.
- [ ] Add importer resume and bound tests.
- [ ] Add retention interaction tests.
- [ ] Add live/archive/mixed-series API tests.
- [ ] Add frontend tests for hydro chart and export labels.

Non-goals and blocked items:

- [ ] Do not claim support for archive families that remain unverified.
- [ ] Do not add unbounded public import triggers.
- [ ] Do not replace missing or invalid measurements with zero.

Acceptance criteria:

- [ ] At least one verified hydro archive family imports through a bounded
  server-side path.
- [ ] Imported hydro observations preserve source quality and missing-value
  metadata.
- [ ] Live/archive/mixed labels remain visible in APIs, charts, and exports.
- [ ] Unsupported archive families remain documented as unsupported.

## Stage 24 - Warning History And Change Timeline

Goal: preserve and explain how warnings change over time.

Implementation tasks:

- [ ] Persist warning snapshots.
- [ ] Define stable warning identity rules.
- [ ] Detect creation, update, extension, escalation, downgrade, cancellation,
  and expiry events.
- [ ] Support meteorological and hydrological warning history.
- [ ] Add a warning-change API.
- [ ] Add timeline UI for warning changes.
- [ ] Add filters by warning type, level, phenomenon, office, and area.
- [ ] Show the relationship between warning changes and station observations
  where useful.
- [ ] Explicitly handle source corrections and duplicated warning records.
- [ ] Define retention policy.
- [ ] Add exports for warning history and change timelines.
- [ ] Preserve attribution and the official-warning disclaimer.

Documentation tasks:

- [ ] Update `ARCHITECTURE.md` with warning identity, snapshot, and retention
  design.
- [ ] Update `API_CONTRACT.md` for warning-history endpoints.
- [ ] Update `UI_UX.md` for the timeline interaction.
- [ ] Update `LEGAL_ATTRIBUTION.md` for exported warning history.
- [ ] Update `README.md` and `TASKS.md` after implementation.

Test tasks:

- [ ] Add backend snapshot and identity tests.
- [ ] Add change-detection tests for creation, update, extension, escalation,
  downgrade, cancellation, expiry, corrections, and duplicates.
- [ ] Add API tests for warning-history filters.
- [ ] Add frontend timeline tests.
- [ ] Add migration and retention tests.
- [ ] Add E2E tests for a warning-change workflow.

Non-goals and blocked items:

- [ ] Do not present MeteoLens as an official warning service.
- [ ] Do not infer official warning changes when the source data is ambiguous;
  expose ambiguity instead.

Acceptance criteria:

- [ ] Warning changes can be reviewed from persisted snapshots.
- [ ] Change categories are deterministic and tested.
- [ ] Timeline UI and exports preserve attribution and disclaimers.
- [ ] Source corrections and duplicated records are explicit.

## Stage 25 - Performance And Scalability Hardening

Goal: document and verify the supported scale of a single MeteoLens deployment.

Implementation tasks:

- [ ] Run frontend bundle analysis.
- [ ] Lazy-load or code-split MapLibre, ECharts, expert tools, and heavy panels
  where measurements justify it.
- [ ] Optimize GeoJSON payload size and rendering behavior.
- [ ] Review API pagination and bounded query behavior.
- [ ] Add or tune cache headers and compression.
- [ ] Review SQLite queries and indexes.
- [ ] Ensure memory-safe GRIB download and decode behavior.
- [ ] Avoid unnecessary full-file copies in memory where practical.
- [ ] Move long-running render/import operations out of synchronous request
  paths where appropriate.
- [ ] Evaluate worker or job-queue options that fit the Docker Compose
  deployment.
- [ ] Measure startup time and cache-warmup behavior.
- [ ] Define resource budgets.
- [ ] Document supported deployment size and regression thresholds.

Documentation tasks:

- [ ] Update `ARCHITECTURE.md` with selected performance boundaries.
- [ ] Update `DEPLOYMENT.md` with resource budgets and supported scale.
- [ ] Update `API_CONTRACT.md` with pagination and bounded-query guidance.
- [ ] Update `docs/products/RASTER_PIPELINE.md` if render behavior changes.
- [ ] Update `TASKS.md` only as work is completed.

Test tasks:

- [ ] Add load tests for map layers.
- [ ] Add load tests for exports.
- [ ] Add load tests for history queries.
- [ ] Add load tests for archive imports.
- [ ] Add load tests for product renders.
- [ ] Add regression thresholds with measurable limits, not vague
  "performance improved" statements.

Non-goals and blocked items:

- [ ] Do not introduce Kubernetes-only dependencies for the reference scale.
- [ ] Do not optimize by hiding data-quality metadata or attribution.

Acceptance criteria:

- [ ] Supported single-deployment scale is documented with measured limits.
- [ ] Expensive routes have measurable budgets and regression thresholds.
- [ ] Bundle, GeoJSON, database, render, and import bottlenecks are measured.
- [ ] Performance changes preserve attribution, missing-value metadata, and
  known-limitations visibility.

## Stage 26 - PDF Reports And Shareable Weather Briefings

Goal: generate shareable reports without losing data-quality context or
attribution.

Implementation tasks:

- [ ] Add station reports.
- [ ] Add location reports.
- [ ] Add warning reports.
- [ ] Add selected time-range reports.
- [ ] Include maps and charts.
- [ ] Include source timestamps.
- [ ] Include retrieval timestamps.
- [ ] Include data delay.
- [ ] Include missing-value metadata.
- [ ] Include imported/live-series labels.
- [ ] Include IMGW-PIB, PRG/GUGiK, and WMO OSCAR/Surface attribution where
  applicable.
- [ ] Include processed-data notices.
- [ ] Include the official-warning disclaimer.
- [ ] Design an accessible print layout.
- [ ] Choose a server-side generation model.
- [ ] Apply resource and abuse limits from Stages 19 and 25.
- [ ] Generate sample reports only from fixtures in CI.

Documentation tasks:

- [ ] Update `docs/power-user/PDF_EXPORT_PLAN.md`.
- [ ] Update `API_CONTRACT.md` for report endpoints.
- [ ] Update `UI_UX.md` for report controls and print layout.
- [ ] Update `LEGAL_ATTRIBUTION.md` for report attribution and metadata.
- [ ] Update `README.md` and `TASKS.md` after implementation.

Test tasks:

- [ ] Add deterministic report-generation tests.
- [ ] Add fixture-only CI sample report tests.
- [ ] Add accessibility and print-layout checks where practical.
- [ ] Add tests for timestamps, missing metadata, imported/live labels,
  attribution, processed-data notices, and disclaimers.
- [ ] Add abuse/resource-limit tests.

Non-goals and blocked items:

- [ ] Do not describe PDF reports as implemented until server-side generation,
  docs, and tests land.
- [ ] Do not generate CI samples from live IMGW data.
- [ ] Do not omit known limitations or data-quality metadata from reports.

Acceptance criteria:

- [ ] Reports are generated server-side within documented resource limits.
- [ ] Reports preserve source timestamps, retrieval timestamps, delay,
  missing-value metadata, attribution, processed-data notices, and disclaimers.
- [ ] CI sample reports are deterministic and fixture-based.
- [ ] PDF reports remain shareable alpha outputs, not official warnings.
