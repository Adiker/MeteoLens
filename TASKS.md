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
- [x] Capture populated-cache screenshots or demo media for `README.md`.

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

- [ ] Research legal/public TERYT administrative boundary datasets.
- [ ] Research legal/public hydrological basin or catchment geometry datasets.
- [ ] Research official station metadata or station coordinate lists for
  synoptic stations.
- [ ] Add a source/legal review checklist for every external geometry dataset.
- [ ] Design geometry import and cache pipeline.
- [ ] Map meteorological warning TERYT codes to polygons.
- [ ] Map hydrological warning basin or area codes to geometries where possible.
- [ ] Reconcile synoptic station coordinates from an official or legally cleared
  station metadata source.
- [ ] Add warning polygons on the map.
- [ ] Add spatial matching for "My location" warnings.
- [ ] Add province, county, and basin filters where geometry exists.
- [ ] Clearly show missing geometry where mapping cannot be resolved.

## Stage 10 - Radar, Product Files, GRIB, And Timeline Animation

- [ ] Research IMGW product API file types and identify high-value products.
- [ ] Document product IDs that are stable, unstable, missing, or legally or
  technically risky.
- [ ] Research radar-like products such as CAPPI, SRI, and MERGE if available
  from public sources.
- [ ] Research GRIB/model files if available from public sources.
- [ ] Defer binary parsing until formats, projection, licensing, file size, and
  cache strategy are documented.
- [ ] Design raster/product ingestion pipeline.
- [ ] Design tile generation or raster rendering strategy for MapLibre.
- [ ] Add timeline and animation requirements for radar/product frames.
- [ ] Add cache retention policy for large product files.
- [ ] Add explicit UI labels for source time, frame time, missing frames, stale
  frames, and processed-data notice.

## Stage 11 - PWA, Local Alerts, Dashboards, And Power-User Features

- [ ] Add PWA support planning.
- [ ] Add saved locations.
- [ ] Add saved map views.
- [ ] Add user-defined dashboards.
- [ ] Add local alert rules based on active warnings, thresholds, stale data,
  and nearby stations.
- [ ] Add source availability dashboard.
- [ ] Add data freshness monitor.
- [ ] Add advanced expert filters.
- [ ] Add warning-vs-measurement comparison.
- [ ] Add trend and anomaly detection ideas.
- [ ] Add generated public API client task from OpenAPI.
- [ ] Keep alerting clearly separated from official warning responsibility;
  MeteoLens must not present itself as an official alerting system.
