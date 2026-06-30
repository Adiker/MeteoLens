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

Planned frontend module layout:

- `src/app`: application shell, routing, providers.
- `src/map`: MapLibre map, layer registry, legends, selection handling.
- `src/features/stations`: station lists, details, charts, exports.
- `src/features/warnings`: warning layers, details, filters.
- `src/features/location`: "My location" workflow.
- `src/features/timeline`: time controls and play/pause animation.
- `src/api`: typed client and TanStack Query hooks.
- `src/state`: Zustand stores for view and preferences.
- `src/components`: shared UI components.

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

PostGIS can later replace geometry references with native geometry columns.
TimescaleDB can later optimize observation history.

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
- cache tests for freshness and failed fetch behavior,
- refresh endpoint test with a patched IMGW client.

Stage 4-5:

- API contract tests,
- map layer rendering tests,
- export tests,
- basic E2E flows for map, selection, filters, details, and permalink.

Stage 4 adds backend API and export tests using normalized cache records seeded
from real-shape IMGW fixtures.

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

## Observability

MVP should log:

- source fetch success/failure,
- parser version and parser warnings,
- cache freshness,
- API latency,
- export generation errors.

Later stages can add structured logs, metrics, tracing, and dashboard panels for
source availability.

## Extension Points

- Additional public data sources after legal review.
- Radar products after product endpoint and file format research.
- GRIB/model products through dedicated parsers and tiling/rendering pipeline.
- Local alerting and PWA.
- PDF report generation.
