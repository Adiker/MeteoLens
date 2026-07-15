# ARCHITECTURE.md - MeteoLens

## Context

MeteoLens is a map-first web application for public IMGW-PIB data. It should be
more useful than raw tables by combining current measurements, warnings,
metadata, map layers, charts, exports, and explicit data-quality information.

The application must use real public sources. Mock data is allowed only in tests
or isolated stories, never as the final implementation.

## Stack

Frontend:

- React + TypeScript + Vite for a single-page map dashboard.
- Tailwind CSS + shadcn/ui for accessible, composable UI primitives.
- MapLibre GL for map layers, GeoJSON, future raster/tile support, and scalable
  styling.
- Apache ECharts for station time series and comparisons.
- TanStack Query for API state and request caching.
- Zustand for view state: map camera, active layers, filters, theme, selected
  object, simple/expert mode, and permalink state.

Backend:

- FastAPI for typed HTTP endpoints.
- Pydantic for external payload parsing and internal API schemas.
- httpx for IMGW requests.
- SQLite for MVP persistence.
- Alembic migrations with a model design that can move to
  PostgreSQL/PostGIS/TimescaleDB.
- Scheduler for recurring source refreshes.

## Project Structure

```text
frontend/       React/Vite application, map UI, charts, export UI
backend/        FastAPI app, IMGW clients, parsers, normalizers, cache, API
packages/       Repo-local API client packages and generated OpenAPI metadata
data/           Local cache/database files and non-secret downloaded datasets
docs/           Screenshots, mockups, diagrams, research notes
scripts/        Developer and data maintenance scripts
deploy/         Docker, production, reverse proxy, observability assets
.github/        CI workflows and issue/PR templates
```

## Backend Modules

Planned backend module layout:

- `app/core`: config, logging, time utilities, errors.
- `app/imgw/client`: HTTP client, retries, headers, response metadata.
- `app/imgw/parsers`: source-specific parsers for synop, hydro, meteo,
  warnings, products, and archives.
- `app/normalization`: shared internal models and field/unit conversion.
- `app/cache`: raw payload storage, normalized rows, freshness metadata.
- `app/db`: database engine, migrations, repositories.
- `app/api`: public API routes for frontend.
- `app/export`: CSV, JSON, GeoJSON, and later PDF/PNG support.

## Frontend Modules

Stage 5 frontend module layout (implemented):

- `src/app`: application shell and providers (`QueryClientProvider`), wiring the
  theme, permalink, and keyboard-shortcut hooks.
- `src/map`: MapLibre map (`MapShell`) with the stations GeoJSON source, circle
  layer coloured by station type, selection highlight, and PNG/flyTo handlers.
- `src/components`: header/search/export controls, control panel (layer toggles,
  legends, filters, warning list, source status), details panel (station and
  warning, simple/expert, mobile bottom sheet), ECharts station chart, shortcut
  help, attribution bar, and shared primitives.
- `src/api`: typed client (`client.ts`) and TanStack Query hooks (`queries.ts`).
- `src/store`: Zustand store for layers, selection, mode, theme, filters, map
  view, and location.
- `src/hooks`: theme, permalink sync, and global keyboard shortcuts.
- `src/lib`: layer registry, formatting helpers, permalink (de)serialization,
  and the window-event map command bus.

Imperative map commands (search/location fly-to, PNG capture) use a small
window-event bus (`src/lib/mapBus.ts`) instead of prop-drilling the MapLibre
instance. The timeline is now driven by cached product frame manifests and, for
the reviewed COSMO rendering path, can opt into a MapLibre image overlay.
Meteorological warning polygons render where reviewed PRG geometry resolves the
TERYT codes, and Stage 18 adds reviewed WMO OSCAR/Surface coordinates for
synop station markers. Hydrological warnings remain list-only until a reviewed
basin dataset is added.

Stage 16 added a repo-local TypeScript integration client under
`packages/meteolens-api-client/`. The frontend still uses its local
`src/api/client.ts` for app-specific UI types and TanStack Query integration;
the package is for external scripts, examples, and OpenAPI drift checks.

## Data Ingestion Flow

1. Scheduler or on-demand request selects a source.
2. IMGW client fetches data and records URL, status, headers, retrieval time,
   duration, and error details.
3. Raw response is cached before parsing when feasible.
4. Source parser validates raw shape and converts strings/nulls into typed
   fields.
5. Normalizer maps source records into internal station, observation, warning,
   product, or archive models.
6. Cache/database stores normalized records with source metadata.
7. API serves frontend-ready objects with source, retrieval, observation,
   missing-field, and processed-data metadata.

Stage 3 implements the client, parser, normalization, and file-cache portions of
this flow for current IMGW JSON endpoints. Stage 4 exposes map, station,
warning, location summary, and export API endpoints backed by those normalized
records. If cache is empty, these endpoints return an explicit empty state or a
cache-specific error rather than mock data.

## Normalization Rules

- Preserve source IDs.
- Preserve raw values in expert metadata when feasible.
- Convert numeric strings to numbers only when parsing is unambiguous.
- Preserve `null` and missing fields separately where the source allows it.
- Never replace missing measurements with zero.
- Compute `data_delay` from observation timestamp and retrieval timestamp.
- Mark transformed data with `processed_notice`.

## Cache Strategy

MVP cache stores:

- source key and URL,
- raw body or raw archive file reference,
- HTTP status and selected headers,
- retrieval timestamp,
- parser version,
- normalized payload hash,
- parser warnings/errors,
- last successful refresh.

Cache files are written atomically (temp file + rename), so API readers never
observe truncated JSON while a startup or scheduled refresh rewrites a source.

Suggested TTL defaults:

- synop: 10 minutes,
- hydro: 10 minutes,
- meteo: 10 minutes,
- warnings: 5 minutes,
- product list: 60 minutes,
- archives: manual or daily refresh.

Final TTLs must be revisited after observing source behavior.

The current backend includes a startup refresh path controlled by
`METEOLENS_SYNC_ON_STARTUP`. When enabled, it fetches each configured IMGW JSON
source, parses it through the source-specific parser layer, and writes the
normalized file cache used by the public API. Per-source fetch or parser errors
are stored as cache errors; stale successful payloads are preserved when
available.

A periodic in-process scheduler (`app/imgw/scheduler.py`) is controlled by
`METEOLENS_REFRESH_ENABLED`. When enabled, the app lifespan starts one refresh
loop per source; each loop waits its configured interval
(`METEOLENS_REFRESH_SYNOP_SECONDS`, `METEOLENS_REFRESH_HYDRO_SECONDS`,
`METEOLENS_REFRESH_METEO_SECONDS`, `METEOLENS_REFRESH_WARNINGS_SECONDS`; other
sources fall back to their default TTL) and then re-runs the same
fetch/parse/cache path used at startup, which also appends station observation
history rows. Loops log failures without masking them and shut down cleanly on
app shutdown. The first scheduled refresh happens one interval after startup;
initial freshness comes from the startup sync.

Stage 8 added an observation-history cache instead of replacing each station
with only the latest snapshot. Historical rows keep source timestamp, retrieval
timestamp, data delay, missing/null state, attribution, processed-data notice
metadata, and a local retention policy so the cache does not grow unbounded.

Stage 15 added an opt-in server-side archive importer for daily SYNOP archives.
`app/imgw/archive.py` discovers bounded archive ZIPs, decodes CP1250/CSV daily
SYNOP rows, preserves status-driven missing/null values, and writes through the
observation-history repository. Imports are limited by date range and file count,
rate-limited between files, and resumable through upserts on
`station_id + metric + observed_at + origin`. Including `origin` prevents a
daily archive point from overwriting a live refresh at the same normalized UTC
timestamp. Existing SQLite databases are rebuilt in place to use this key while
preserving rows and indexes. Archive downloads are streamed with a hard byte
limit; ZIP entry count, per-entry uncompressed size, total uncompressed size, and
CSV row count are checked before and during extraction so ZIP bombs and oversized
payloads fail the import run with an explicit error.

The Stage 21 reconciliation follow-up adds
`app/imgw/station_mapping.py` and the versioned
`app/imgw/data/synop_station_mapping.v1.json`. The reproducible fetch script
parses the official IMGW station catalogue, groups duplicate source rows by
`NSP`, derives a block-12 candidate only from the explicit station code, and
requires an exact current IMGW SYNOP `id_stacji`. Ambiguous candidates fail the
build. Runtime archive parsing accepts only reviewed `mapped` entries;
unresolved rows use `synop-archive:<NSP>` and emit a parser warning.
Before a controlled backfill, legacy pre-map `archive_import` rows are also
reconciled through the same reviewed artifact, so upgraded persistent databases
do not require a manual identifier list or destructive reset.

Stage 19 classifies read-only data routes as public, product renders as
expensive, and archive imports as administrative. The archive HTTP endpoint is
disabled without a deployment-local admin token; MeteoLens stores no user
accounts. Product work is bounded by a cache-aware render gate, while archive
imports use a one-at-a-time gate plus duplicate-range cooldown. Product binary
downloads validate every manifest URL immediately before HTTP: HTTPS only,
approved IMGW host/path, and a public DNS resolution that rejects loopback,
link-local, and private addresses. Cached manifests or binaries do not bypass
those checks. Nginx enforces
public internet request limits before requests reach the backend. The documented
Caddy TLS edge proxies every path through nginx on port 8080; nginx accepts
forwarded client addresses only from configured trusted proxy ranges so its
per-IP limit key remains both accurate and resistant to direct-header spoofing.
The one-shot data initializer temporarily owns `/data` while seeding or merging
bundled geometry, then returns the volume to backend UID/GID 10001.

Stage 10 defines a separate cache policy for large product, radar-like,
and GRIB files. Detail manifest cache lives under `cache/product_details/`
(TTL plus a manifest-count cap, refreshed by the scheduler when
`METEOLENS_PRODUCT_REFRESH_ENABLED=true`). Stage 14 added the binary and render
caches: downloaded COSMO GRIB files under `data/products/binaries/{id}/` and
rendered PNG frames plus metadata sidecars under `data/products/renders/{id}/`,
both with count and age eviction. The rendering pipeline lives in
`app/products/` — `grib1.py` (narrow pure-Python GRIB1 reader), `rotated_grid.py`
(rotated-pole transforms and Web-Mercator resampling), `png.py` (dependency-free
RGBA PNG writer with iTXt metadata), `rendering.py` (variable registry,
download with size cap and redirect/HTML detection, grid verification against
the reviewed COSMO grid, palette, retention), and `refresh.py` (detail-manifest
refresh with optional prefetch). Limits and behavior are documented in
`docs/products/RASTER_PIPELINE.md`.

## Database Schema

MVP SQLite tables should include:

- `source_fetches`: request metadata, raw payload reference, status, error.
- `stations`: source, source ID, name, type, coordinates, region metadata.
- `observations`: station ID, metric, value, unit, observed_at, retrieved_at,
  raw field name, missing flag.
- `warnings`: source ID, category, level, probability, valid_from, valid_to,
  published_at, office, text, comment.
- `warning_areas`: warning ID, area type, TERYT or basin code, label,
  optional geometry reference.
- `exports`: export type, filters, created_at, source attribution metadata.

PostgreSQL/PostGIS and TimescaleDB remain later migration targets for geometry
and observation history.

Stage 8 observation-history design should refine `observations` so repeated
fetches become a real time series rather than a single latest value. Required
query dimensions include station, metric, observed time range, aggregation
interval, and result limit. The first implementation may stay on SQLite, but
schema and repository boundaries should leave room for PostgreSQL/PostGIS and
TimescaleDB.

Stage 15 extends `observation_history` with `origin`, `import_run_id`, and
`import_source_url`. The Stage 21 mapping follow-up adds `source_station_id`,
`station_mapping_status`, `station_mapping_version`,
`station_mapping_source_url`, and `station_mapping_retrieved_at`. Live refresh
rows use `origin='live_refresh'`; imported archive rows use
`origin='archive_import'`; aggregated API responses may report `mixed`.
`archive_import_runs` records run status, observed range, file progress,
insert/update/unchanged counts, warnings, errors, attribution, and processed-data
notice. Archive and live rows share `synop:<id_stacji>` only through an approved
map entry. Unmapped rows remain separate, and no name-based or hardcoded merge
is allowed.

Stage 9 geometry design should add imported geometry metadata without mixing
external dataset ingestion into IMGW parsers. Candidate tables include:

- `geometry_sources`: dataset name, provider, license/terms review status,
  retrieved_at, version, and attribution.
- `admin_boundaries`: TERYT code, area type, name, geometry reference.
- `basin_geometries`: basin or catchment code, name, geometry reference.
- `station_coordinates`: source key, station source ID, coordinate source,
  reconciliation status, and confidence notes.
- `warning_geometry_links`: warning area code to geometry reference, including
  unresolved/missing status.

PostGIS can later replace geometry references with native geometry columns.
Missing or ambiguous geometry must remain visible in API and UI metadata.

Stage 10 product/raster design may add manifest, frame, and tile metadata after
source research:

- `product_manifests`: product ID, file list metadata, retrieval status, risk
  classification, and source timestamps.
- `product_frames`: product ID, frame time, source time, file reference,
  projection metadata, parser status, and missing/stale flags.
- `raster_tiles`: generated tile or rendered raster references, zoom ranges,
  style metadata, and retention policy.

## Public API

The frontend API contract is specified in `API_CONTRACT.md`. All object
responses must include:

- `source`,
- `retrieved_at`,
- source-specific observation/published timestamps where available,
- `data_delay` where computable,
- `missing_fields`,
- `processed_notice`,
- stable IDs for permalinks.

Stage 4 API endpoints read from the normalized file cache written by source
refreshes:

- `/api/v1/map/layers`
- `/api/v1/stations`
- `/api/v1/stations/{id}`
- `/api/v1/stations/{id}/observations`
- `/api/v1/warnings`
- `/api/v1/warnings/{id}`
- `/api/v1/location/summary`
- `/api/v1/export/station/{id}.csv`
- `/api/v1/export/station/{id}.json`
- `/api/v1/export/map.geojson`

Stage 15 added `POST /api/v1/archive/backfill/synop-daily` for manual bounded
imports and extends station observation responses/exports with
`series_origin`, `origin_counts`, and per-point archive import metadata.

Stage 16 stabilized the public `/api/v1` surface in `API_CONTRACT.md`, added
responsible-use and backwards-compatibility notes, and added:

- `/api/v1/export/station/{id}/observations.csv`
- `/api/v1/export/station/{id}/observations.json`
- `/api/v1/export/warnings.geojson`
- `/api/v1/export/map-state.json`

OpenAPI metadata for the TypeScript client is generated from the FastAPI app by
`scripts/api/generate_ts_client.py` and committed at
`packages/meteolens-api-client/src/generated.ts`.

## Map Layers

MVP layers:

- synoptic stations,
- hydrological stations,
- meteorological stations,
- meteorological warnings,
- hydrological warnings.

Hydrological and meteorological stations are emitted as GeoJSON point features
when IMGW coordinates are present. Synoptic records lack coordinates in the
public endpoint; Stage 18 fills them from the reviewed WMO OSCAR/Surface
`synop_stations` dataset bundled in `data/geometry/` (recorded in
`coordinate_source`), while any future unresolved ID stays in missing-geometry
metadata. Warning TERYT codes resolve to polygons via the reviewed PRG
voivodeship/county datasets bundled in `data/geometry/`; hydro basin codes
remain marked as missing area geometry until a reviewed basin dataset is added.

Stage 13 geometry components live in `backend/app/geometry/`:

- `loader.py` reads the format_version 2 manifest, refuses datasets without an
  approved review (`dataset_not_reviewed`) or failing structural validation
  (`invalid_dataset`), and exposes review metadata through
  `/api/v1/geometry/datasets`.
- `validation.py` checks GeoJSON structure, per-dataset geometry types,
  required identifier/name properties, TERYT patterns and coverage, duplicate
  codes, and Poland coordinate bounds.
- `import_cli.py` (`python -m app.geometry.import_cli`) validates and installs
  reviewed datasets with metadata files from `docs/geometry/metadata/`;
  `scripts/geometry/convert_prg_shapefiles.py` reproduces the PRG conversion.

Post-MVP layers:

- archive observations,
- radar products,
- GRIB/model products,
- heatmaps/interpolations,
- trend and anomaly layers.

Stage 9 turns warning area codes into polygons only where a legal/public
geometry dataset exists and the code mapping is reliable. Unresolved TERYT,
basin, or station-coordinate mappings must be returned as partial data, not
silently dropped.

Stage 10 raster/product layers should be designed as time-aware layers with
source time, frame time, missing-frame state, stale-frame state, attribution, and
processed-data notice visible in the API and UI. MapLibre rendering may use
pre-generated tiles, GeoTIFF/raster rendering, or another documented strategy
after source research.

## Export Pipeline

Exports are produced by backend endpoints except PNG map capture, which may be
frontend-generated from the current MapLibre canvas and annotated with source
metadata.

Required export metadata:

- IMGW-PIB source attribution,
- processed-data notice when relevant,
- retrieval timestamp,
- filters and selected object IDs,
- generated timestamp,
- list of missing fields when applicable.

Stage 4 implements station CSV, station JSON, and map GeoJSON exports from
normalized cache records. The map GeoJSON export includes point features and
foreign members for non-spatial warning records and missing-geometry metadata.

Stage 16 extends exports with station observation range CSV/JSON, warning
GeoJSON, and map-state JSON. Warning GeoJSON preserves unresolved warning
geometry in `non_spatial_records` and `missing_geometry`; map-state JSON records
visible layers, map view, mode/theme, selection, filters, timeline state, cache
state, and per-layer feature/record/missing-geometry counts. PDF reports remain
planned only in `docs/power-user/PDF_EXPORT_PLAN.md`.

## Error Handling

- IMGW download errors are user-visible.
- Parser errors are stored with source metadata.
- API responses should distinguish source unavailable, parser failed, no data,
  and unsupported source.
- Frontend must show loading, empty, stale, partial, and error states.

## Testing Strategy

Stage 2:

- backend healthcheck tests,
- frontend smoke/component tests,
- lint and format scripts.

Stage 3:

- parser tests for every current IMGW source using real captured fixtures,
- normalizer tests for nulls, numeric strings, timestamps, and missing fields,
- cache tests for freshness and failed fetch behavior.

Stage 4-5:

- API contract tests,
- map layer rendering tests,
- export tests,
- basic E2E flows for map, selection, filters, details, and permalink.

Stage 4 adds backend API and export tests using normalized cache records seeded
from real-shape IMGW fixtures.

Stage 16 added backend tests for warning GeoJSON and map-state exports, a
generated-client metadata drift check for public routes, and syntax checks for
the Node API examples when Node.js is available.

Stage 6:

- backend parser/API edge-case tests (malformed payloads, bbox/date-range
  filters, cache_invalid handling) — see `backend/tests/`,
- frontend component tests for `DetailsPanel`, `StationChart`, `ExportMenu`,
  `SearchBox`, `HeaderBar`, `ShortcutHelp`, `LocationSummary`, keyboard
  shortcuts, and the app store,
- E2E tests (`frontend/e2e/`, run via `npm run test:e2e`) using Playwright.
  `playwright.config.ts` starts the real backend and frontend dev servers; the
  backend cache is seeded from `backend/tests/fixtures` by
  `backend/tests/e2e_seed_cache.py` so the suite exercises real API responses
  without calling out to IMGW-PIB. Wired into CI as the `e2e` job.

The CI workflow first classifies changed paths. Documentation-only PRs keep the
lightweight change-detection job, while backend, frontend, and E2E jobs run only
when their code, compose files, or the CI workflow itself changes.

## Deployment

Stage 2 introduced Docker Compose with:

- backend service,
- frontend service,
- SQLite volume for MVP,
- healthcheck,
- `.env.example`,
- production notes for reverse proxy and persistent storage.

Post-MVP deployment may add PostgreSQL/PostGIS/TimescaleDB and object storage
for large raw products.

Stage 7 split local development deployment from production deployment.
Production serves the frontend as static built assets through nginx instead of
the Vite dev server. The backend production image avoids development-only
dependencies.

Stage 7 deployment documentation covers reverse proxy/TLS, production CORS,
restart policies, persistent volumes, backup expectations, source fetch
retry/backoff behavior, and a public deployment checklist. Public or commercial
deployments remain blocked on verifying current IMGW-PIB terms and choosing a
project license.

Stage 10 deployment planning must cover large product-file storage, cache
retention, tile/raster generation storage, and operational limits before any
radar or GRIB product layer is exposed.

Stage 19 closed the security portion of the gap between a public repository and
an unrestricted public deployment: endpoint classification, admin
authentication, rate and concurrency limits, proxy safeguards, non-root
containers, and workflow restrictions. Stage 20 adds observability, backups,
and restore tests; Stage 21 current-main release validation is recorded in
`docs/release/STAGE_21_VALIDATION_2026-07-14.md`. Tagging remains pending.

GitHub Actions use a fixed Ubuntu 24.04 runner and commit-pinned actions. Backend
CI installs the lockfile-resolved Python 3.12 environment with `uv`, while npm
continues to use `npm ci` for frontend and Playwright E2E jobs. Path filtering
keeps the MeteoLens backend/frontend split, and security CI adds dependency,
secret, and production-backend-image scans. Dependabot checks action pins daily.

## Observability

MVP should log:

- source fetch success/failure,
- parser version and parser warnings,
- cache freshness,
- API latency,
- export generation errors.

Later stages can add structured logs, metrics, tracing, and dashboard panels for
source availability.

Stage 7 defined production logging and monitoring requirements for source
fetches, parser failures, stale cache, and API errors. Stage 11 added a
user-facing source availability dashboard and data freshness monitor from the
same underlying metadata. Stage 20 provides explicit liveness/readiness endpoints,
low-cardinality OpenMetrics instrumentation, JSON request-correlated logs, and
a private optional Prometheus profile. Source outages produce a degraded
readiness state while stale cache continues to serve; SQLite or `/data` failures
produce `503 not_ready`. Storage gauges report SQLite, cache, geometry, product
files, and `/data` disk usage. `app.operations.backup` uses SQLite's backup API
for portable backups and validates checksums plus `PRAGMA integrity_check`
before restore. Stage 25 remains responsible for measured performance and
scalability thresholds.

## Extension Points

- Additional public data sources after legal review.
- Radar products after product endpoint and file format research.
- GRIB/model products through dedicated parsers and tiling/rendering pipeline.
- Local alerting and PWA.
- PDF report generation.
- Saved locations, saved views, and user dashboards.
- Generated public API client from OpenAPI after the API stabilizes.
