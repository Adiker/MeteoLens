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
packages/       Shared schemas or generated clients after the API stabilizes
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
instance. The timeline/animation module is deferred until time-aware data
exists, and warning polygons are deferred until area geometry datasets are
cached (warnings currently render as a filterable list).

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

Stage 8 should add an observation-history cache instead of replacing each
station with only the latest snapshot. Historical rows must keep source
timestamp, retrieval timestamp, data delay, missing/null state, attribution, and
processed-data notice metadata. A local retention policy is required before this
cache is allowed to grow unbounded.

Stage 10 should define a separate cache policy for large product, radar-like,
and GRIB files. Do not download or retain large binary products until product
IDs, file formats, projections, licensing, file sizes, and cache eviction rules
are documented.

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

Planned public API changes:

- Stage 8 should expand `/api/v1/stations/{id}/observations` into real
  time-series queries with `metric`, `from`, `to`, `interval`, and `limit`, and
  should add station comparison, rankings, and time-range export endpoints after
  `API_CONTRACT.md` is updated.
- Stage 9 should expose geometry status for warning areas, support spatial
  warning matching for `/api/v1/location/summary`, and add administrative or
  basin filters only for datasets that pass source/legal review.
- Stage 10 should add product/raster/timeline API contracts only after product
  file formats, projections, licensing, cache policy, and missing-frame behavior
  are documented.
- Stage 11 should add saved views, dashboards, local alert rules, and generated
  API client planning only after the data ownership and official-warning
  disclaimer requirements are documented.

## Map Layers

MVP layers:

- synoptic stations,
- hydrological stations,
- meteorological stations,
- meteorological warnings,
- hydrological warnings.

Hydrological and meteorological stations are emitted as GeoJSON point features
when IMGW coordinates are present. Synoptic records currently lack coordinates
in the public endpoint and are therefore listed in missing-geometry metadata
unless a future source provides lat/lon. Warning records are exposed with TERYT,
basin, or province area codes and marked as missing area geometry until TERYT
and basin geometry datasets are added.

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

## Deployment

Stage 2 should introduce Docker Compose with:

- backend service,
- frontend service,
- SQLite volume for MVP,
- healthcheck,
- `.env.example`,
- production notes for reverse proxy and persistent storage.

Post-MVP deployment may add PostgreSQL/PostGIS/TimescaleDB and object storage
for large raw products.

Stage 7 should split local development deployment from production deployment.
Production should serve the frontend as static built assets through nginx,
Caddy, or an equivalent server instead of the Vite dev server. The backend image
should be production-oriented and avoid development-only dependencies.

Stage 7 deployment documentation must cover reverse proxy/TLS, production CORS,
restart policies, persistent volumes, backup expectations, source fetch
retry/backoff behavior, and a public deployment checklist. Public or commercial
deployments remain blocked on verifying current IMGW-PIB terms and choosing a
project license.

Stage 10 deployment planning must cover large product-file storage, cache
retention, tile/raster generation storage, and operational limits before any
radar or GRIB product layer is exposed.

## Observability

MVP should log:

- source fetch success/failure,
- parser version and parser warnings,
- cache freshness,
- API latency,
- export generation errors.

Later stages can add structured logs, metrics, tracing, and dashboard panels for
source availability.

Stage 7 should define production logging and monitoring requirements for source
fetches, parser failures, stale cache, and API errors. Stage 11 may build a
user-facing source availability dashboard and data freshness monitor from the
same underlying metadata.

## Extension Points

- Additional public data sources after legal review.
- Radar products after product endpoint and file format research.
- GRIB/model products through dedicated parsers and tiling/rendering pipeline.
- Local alerting and PWA.
- PDF report generation.
- Saved locations, saved views, and user dashboards.
- Generated public API client from OpenAPI after the API stabilizes.
