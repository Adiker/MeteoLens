# API_CONTRACT.md - MeteoLens Backend API

Base path: `/api/v1`.

This is the supported public API contract for the current alpha. The API is
cache-backed: data comes from public IMGW-PIB sources fetched server-side,
normalized by MeteoLens, and returned with attribution, retrieval timestamps,
missing-field metadata, and processed-data notices.

## Versioning And Compatibility

- `/api/v1` is the stable alpha surface. Additive response fields and additive
  optional query parameters may appear in `v1`.
- Removing fields, changing field meaning, changing default filter behavior, or
  changing export column names requires a new API version or an explicit
  migration note in `CHANGELOG.md`.
- Clients should ignore unknown JSON fields and should not treat collection
  ordering as stable unless an endpoint documents it.
- Error bodies use FastAPI's `{"detail": {"error": ...}}` envelope for
  application errors.
- `GET /openapi.json` is the machine-readable source of truth. The lightweight
  TypeScript client metadata in
  `packages/meteolens-api-client/src/generated.ts` is generated from this
  OpenAPI schema with `python scripts/api/generate_ts_client.py`.

## Responsible Use

- Route categories are deliberately small and deployment-visible: **public**
  (read-only health/data/map/export/product-metadata routes), **expensive**
  (product rendering), and **administrative** (archive backfill).
- Production nginx limits public API traffic to 60 requests/minute/IP (burst
  30) and product renders to 10 requests/minute/IP (burst 2).
- Public users should call MeteoLens, not IMGW archive/product files directly.
  Product rendering has a configurable one-render default concurrency bound and
  coalesces simultaneous identical requests. Archive import is single-concurrent
  and suppresses recently completed duplicate date ranges.
- MeteoLens local alerts, dashboards, and warning/station comparisons are not
  official IMGW-PIB warnings and must keep the disclaimer visible in UI and
  downstream integrations.

## Shared Metadata

All data responses should include source metadata:

```json
{
  "source": {
    "provider": "IMGW-PIB",
    "source_key": "synop",
    "url": "https://danepubliczne.imgw.pl/api/data/synop",
    "retrieved_at": "2026-06-29T21:10:00Z",
    "attribution": "Źródło danych: IMGW-PIB.",
    "processed_notice": "Dane IMGW-PIB zostały przetworzone przez MeteoLens."
  }
}
```

Common object fields:

- `id`: stable MeteoLens ID.
- `source_id`: source-provided ID.
- `observed_at`: measurement timestamp if applicable.
- `published_at`: warning publication timestamp if applicable.
- `retrieved_at`: backend fetch timestamp.
- `data_delay_seconds`: computed where possible.
- `missing_fields`: source fields absent or explicitly `null`.
- `raw_available`: whether expert raw JSON can be requested.

Collection responses include:

- `generated_at`: response generation timestamp.
- `cache`: per-source cache status with freshness, record count, parser
  warnings, and error metadata.
- `empty_state`: present when no normalized cached records are available or no
  records match a narrow filter.

When normalized cache is empty, collection endpoints return an explicit
`empty_state` instead of mock data. Detail endpoints return `503` with
`cache_empty` if no relevant cache exists, or `404` with `not_found` when cache
exists but the requested object is absent.

## Health

`GET /health`

Backward-compatible liveness endpoint. `GET /health/live` has the same
response and is the explicit liveness probe.

```json
{
  "status": "ok",
  "service": "meteolens-backend",
  "version": "0.1.0-alpha"
}
```

`GET /health/ready`

Checks completed startup, SQLite access, and write access to `/data`. It returns
`200` with `status: "ready"` or `"degraded"`; degraded IMGW cache never makes
the cached application unavailable. It returns `503` with `"not_ready"` only
when a core dependency cannot serve data. The `checks` object exposes safe
status codes for `startup`, `database`, `data`, and `sources`.

`GET /metrics`

Prometheus/OpenMetrics endpoint for the private Compose network. It is disabled
unless `METEOLENS_METRICS_ENABLED=true`, excluded from OpenAPI, and deliberately
not proxied by the public nginx service.

## Sources

`GET /api/v1/sources`

Returns supported source descriptors, cache status, and parser status.

Public refresh endpoints are not exposed. Cache refresh remains an internal
backend concern so public API consumers cannot mutate cache state; deployments
can enable startup refresh with `METEOLENS_SYNC_ON_STARTUP=true`.

## Map Layers

`GET /api/v1/map/layers`

Query parameters:

- `layers`: comma-separated layer keys.
- `bbox`: optional `minLon,minLat,maxLon,maxLat`.
- `time`: optional ISO timestamp for time-aware layers.
- `expert`: optional boolean for extra metadata.

Implemented layer keys:

- `synop_stations`
- `hydro_stations`
- `meteo_stations`
- `warnings_meteo`
- `warnings_hydro`

Returns GeoJSON FeatureCollections grouped by layer. Hydro and meteo stations
are point features when coordinates exist. Synop records are emitted as point
features from the reviewed Stage 18 `synop_stations` WMO OSCAR/Surface dataset;
future station IDs not present in that dataset are listed in `missing_geometry`
with `missing_lat_lon`. Warning areas are emitted as polygon features when
their TERYT/basin codes resolve against reviewed geometry datasets (Stage 13
ships PRG voivodeship and county polygons; Stage 22 ships II aPGW-derived
`hydro_basins`). Unresolved codes stay visible in `records` and
`missing_geometry` with `geometry_not_found` (dataset loaded, code unmatched)
or `missing_area_geometry_dataset` (required dataset not installed).

```json
{
  "generated_at": "2026-06-30T07:30:00Z",
  "cache": [],
  "empty_state": null,
  "layers": [
    {
      "key": "hydro_stations",
      "title": "Stacje hydrologiczne",
      "source_keys": ["hydro"],
      "sources": [],
      "geojson": {
        "type": "FeatureCollection",
        "features": []
      },
      "records": [],
      "missing_geometry": []
    }
  ]
}
```

## Stations

`GET /api/v1/stations`

Query parameters:

- `type`: `synop`, `hydro`, `meteo`.
- `q`: text search.
- `bbox`: optional bounding box.
- `limit`: default 200.

Returns:

```json
{
  "generated_at": "2026-06-30T07:30:00Z",
  "cache": [],
  "empty_state": null,
  "stations": [
    {
      "id": "hydro:151140030",
      "source_id": "151140030",
      "source_key": "hydro",
      "station_type": "hydro",
      "name": "Przewoźniki",
      "lat": 51.5253,
      "lon": 14.8217,
      "coordinate_source": null,
      "latest_observed_at": "2026-06-30T07:00:00+02:00",
      "data_delay_seconds": 1800,
      "missing_fields": ["temperatura_wody"],
      "source": {},
      "raw_available": true
    }
  ]
}
```

`coordinate_source` names the reviewed geometry dataset attribution when a
synop station's coordinates were filled from the `synop_stations` dataset
(IMGW's synop API publishes none); it is `null` when coordinates come directly
from the IMGW payload or are missing.

`GET /api/v1/stations/{id}`

Returns station metadata, latest observations, source metadata, and raw metadata
availability. IDs use the normalized stable form, for example
`synop:12295`, `hydro:151140030`, or `meteo:252210290`.

`GET /api/v1/stations/{id}/observations`

Query parameters:

- `metric`: optional metric key.
- `from`: optional ISO timestamp.
- `to`: optional ISO timestamp.
- `interval`: aggregation interval such as `raw`, `10m`, `1h`, or `1d`.
- `limit`: maximum number of returned points.

Returns observation values for charts and exports. The implementation reads
persisted observation history when available and falls back to the latest cache
snapshot when history is empty. Responses include `series_kind` (`history` or
`snapshot`), `series_origin` (`live_refresh`, `archive_import`, or `mixed`),
`origin_counts`, and the requested `interval`. If the current station cache is
empty but archive history exists for the requested stable station ID, this
endpoint may return archive history with source metadata pointing at the archive
directory; map/list station discovery still depends on current cache data and
reviewed geometry.

`mixed` means both origins exist under the same normalized station ID. Daily
SYNOP archive rows may use a current `synop:<id_stacji>` only when their source
`NSP` has a `mapped` entry in the reviewed versioned IMGW mapping artifact.
Unmapped rows use `synop-archive:<NSP>` and never contribute to a current
station's `mixed` series.

Each observation preserves `null` values and includes `missing`,
`raw_field`, `observed_at`, `retrieved_at`, `data_delay_seconds`, and
unit metadata where available. Historical observations may also include
`origin`, `import_run_id`, `import_source_url`, `source_station_id` (the
original archive `NSP`, or the source `id_stacji` for persisted live history),
`station_mapping_status`, `station_mapping_version`,
`station_mapping_source_url`, `station_mapping_retrieved_at`, `archive_kind`,
`quality_status`, `missing_reason`, `temporal_resolution`,
`source_file_sha256`, and `source_file_last_modified`. Mapping status is
`mapped`, `unmapped_not_current_synop`, or
`unmapped_not_in_mapping_source`; the mapping-specific fields are `null` for
live-only points. CODZ points use `temporal_resolution="1d"` and midnight UTC
only as a calendar-day marker, not a measurement hour.

`POST /api/v1/archive/backfill/synop-daily`

`POST /api/v1/archive/backfill/hydro-daily`

Administrative route. It is disabled unless `METEOLENS_ADMIN_TOKEN` is set.
When enabled, clients must send the matching value in the
`X-MeteoLens-Admin-Token` header. Missing configuration returns `403`; missing
or invalid credentials return `401` with `WWW-Authenticate: MeteoLensAdmin`.
This deployment-local token is not an end-user account system.

Query parameters:

- `from`: required date (`YYYY-MM-DD`), inclusive.
- `to`: required date (`YYYY-MM-DD`), inclusive.

The first route imports reviewed daily SYNOP archives. The second imports only
the verified IMGW daily hydrological `CODZ` family: water level, flow, and
water temperature. CODZ discovery converts the requested calendar dates into
hydrological years (November and December belong to the next year), accepts
`codz_RRRR.zip` and `codz_RRRR_WW.zip`, and fails explicitly when no matching
file is published. `ZJAW`, monthly, semi-annual, and annual summary families
are not accepted.

Both routes write into the existing observation-history schema and are bounded by
`METEOLENS_ARCHIVE_BACKFILL_MAX_DAYS` and
`METEOLENS_ARCHIVE_BACKFILL_MAX_FILES`, wait
`METEOLENS_ARCHIVE_BACKFILL_RATE_LIMIT_SECONDS` between files, and never asks
the browser to fetch IMGW archive files directly. Download bytes, ZIP entries,
expanded entry/total size, and CSV rows also have hard configured limits.
Duplicate records are handled
by upsert on `station_id + metric + observed_at + origin`; repeated runs refresh
archive-import metadata without creating duplicate archive observations, while
an equal-time live observation remains a separate point. Import fails if the reviewed
mapping artifact cannot be loaded or validated. An unmapped `NSP` does not fail
the whole bounded run: it is retained under `synop-archive:<NSP>` and reported
in `parser_warnings`.

CODZ identity is exact `hydro:<PSKDSZS>`; station/river names are never mapping
keys. Each source file is parsed completely before one atomic synchronization
updates corrected values and removes source-withdrawn rows for that file's
selected date slice. Identical source duplicates are collapsed and counted;
conflicting duplicates fail the file. A parse or persistence error performs no
withdrawal deletion.

Only one archive import may run per backend process. A successfully completed
date range enters the configured duplicate cooldown; repeating it during that
window returns `429` with `Retry-After`.

Response shape:

```json
{
  "id": "uuid",
  "source_key": "synop",
  "archive_kind": "synop_daily",
  "status": "completed",
  "started_at": "2026-07-05T12:00:00+00:00",
  "finished_at": "2026-07-05T12:00:02+00:00",
  "observed_from": "2026-05-01",
  "observed_to": "2026-05-07",
  "files_total": 1,
  "files_processed": 1,
  "rows_seen": 62,
  "observations_seen": 620,
  "observations_inserted": 620,
  "observations_updated": 0,
  "observations_unchanged": 0,
  "observations_deleted": 0,
  "duplicate_rows": 0,
  "parser_warnings": [],
  "errors": [],
  "attribution": "Źródło danych: IMGW-PIB.",
  "processed_notice": "Dane IMGW-PIB zostały przetworzone przez MeteoLens."
}
```

Errors use the standard error envelope with codes such as
`archive_range_too_large`, `archive_file_limit_exceeded`,
`archive_download_too_large`, `archive_zip_invalid`, `archive_zip_too_many_entries`,
`archive_zip_central_directory_too_large`, `archive_zip_entry_too_large`, `archive_zip_uncompressed_too_large`,
`archive_row_limit_exceeded`, `invalid_time_range`, or
`archive_backfill_failed`. CODZ also returns `archive_files_not_found`,
`archive_row_invalid`, `archive_zip_missing_csv`, or
`archive_conflicting_duplicate` where applicable.

`GET /api/v1/archive/backfill/runs`

Administrative route with optional exact filters `source_key`, `archive_kind`,
and `status`, plus `limit` (1-100). It returns newest runs first, including
current counters and statuses `running`, `completed`,
`completed_with_warnings`, `failed`, or `interrupted`.

`GET /api/v1/archive/backfill/runs/{id}`

Administrative route returning the run plus each source file's URL,
hydrological year, status, start/finish time, SHA-256, source
`Last-Modified`, row/observation counters, duplicate count, warnings and
errors. Runs and running files left after process restart become
`interrupted`; retrying the same range creates a new idempotent run.

`METEOLENS_OBSERVATION_RETENTION_DAYS` prunes only `origin=live_refresh`.
Archive history has no automatic expiry. Operators can count or remove a
selected kind/date range with:

```bash
python -m app.operations.archive_history prune \
  --archive-kind hydro_daily --from 2024-01-01 --to 2024-01-31
```

The command is dry-run unless `--confirm` is present. A verified backup is
required before confirmed cleanup.

`GET /api/v1/stations/compare`

`GET /api/v1/rankings`

`GET /api/v1/export/station/{id}/observations.csv`

`GET /api/v1/export/station/{id}/observations.json`

Station comparison parameters:

- `station_ids`: comma-separated stable station IDs.
- `metric`: required metric key.
- `from`: optional ISO timestamp.
- `to`: optional ISO timestamp.
- `interval`: optional aggregation interval.
- `limit`: optional point limit.

Ranking parameters:

- `metric`: one of supported ranking metrics, for example temperature,
  wind speed, precipitation, or water level.
- `direction`: `highest` or `lowest` where applicable.
- `from`: optional ISO timestamp.
- `to`: optional ISO timestamp.
- `station_type`: optional station type filter.
- `limit`: optional result limit.

Ranking responses preserve source metadata, missing-field metadata, processed-
Ranking logic omits missing values and does not replace them with zero.
Comparisons and rankings accept stable station IDs present only in persisted
history. Archive-only stations remain available through these APIs and exports
without being placed on the map unless reviewed coordinates exist.

## Warnings

`GET /api/v1/warnings`

Query parameters:

- `type`: `meteo`, `hydro`.
- `active_at`: optional ISO timestamp.
- `level`: optional warning level.
- `phenomenon`: optional text/enum filter.
- `teryt`: optional administrative area code.
- `basin`: optional hydrological basin code.
- `province`: two-digit TERYT voivodeship filter; resolves against warning
  area codes and reviewed geometry metadata.
- `county`: four-digit TERYT county filter.

`GET /api/v1/geometry/datasets`

Returns reviewed geometry dataset status from the local `data/geometry/` cache.
Since Stage 13 each dataset entry also exposes the review metadata recorded at
import time: `provider`, `canonical_url`, `license_url`, `attribution`,
`public_use`, `commercial_use`, `redistribution_note`, `update_cadence`,
`known_limitations`, `dataset_version`, `review_status`, and `reviewed_at`,
next to `loaded`, `feature_count`, and `error`. Datasets without an approved
review are never loaded and report a `dataset_not_reviewed` error; datasets
failing validation report `invalid_dataset`.

`GET /api/v1/warnings/{id}`

Returns warning detail, affected areas, geometry references, source metadata, and
raw JSON availability.

Both current-warning endpoints retain their existing fields and add:

- `history_id`: stable local history identifier when the current warning has a
  persisted identity,
- `history_available`: whether retained history detail can be opened,
- `history_started_at`: first local observation time for that history.

These fields do not claim that history exists before the local deployment
started recording successful refreshes.

Warnings expose `area_codes` from IMGW TERYT/basin/province metadata. When
reviewed geometry datasets are cached under `METEOLENS_GEOMETRY_DIR`, map layers
and warning detail responses include resolved polygon GeoJSON plus
`unresolved_areas` for codes that cannot be mapped.

Resolved basin areas may include `mapping_precision`
(`standard` / `refined` / `coarse` / `coastal`) and optional `mapping_method`
from the reviewed `hydro_basins` feature properties. The same fields are copied
onto warning map-layer and export GeoJSON feature properties when present.
Non-`standard` precision values mark approximate IMGW forecasting-area
mappings, not official IMGW warning polygons.

Stage 9 added reviewed geometry references or GeoJSON features for warning
areas where code mapping is reliable. Responses continue to expose
unresolved codes and missing geometry reasons instead of hiding partial data.

### Warning Change History

`GET /api/v1/warning-events`

Returns a prospective, newest-first feed ordered by `detected_at DESC` and then
stable `event_id DESC`. Supported filters are:

- `type`: exact `meteo` or `hydro`,
- `level`: exact normalized warning level,
- `area`: exact source area code,
- `change_kind`: exact event category,
- `from` and `to`: inclusive ISO timestamps applied to `detected_at`,
- `phenomenon` and `office`: case-insensitive text filters,
- `limit`: 1-200, default 100,
- `cursor`: opaque continuation token returned as `next_cursor`.

Events expose `change_kinds`, `changed_fields`, `detected_at`, `effective_at`,
`classification_basis`, `confidence`, source metadata, identity completeness,
the retained normalized/raw version, missing fields, and
`history_started_at`. Supported categories are `first_observed`, `created`,
`appeared_in_source`, `updated`, `extended`, `escalated`, `downgraded`,
`expired`, `removed_from_source`, `reappeared`, `cancelled`, `correction`, and
`duplicate_conflict`. Categories that require an explicit source signal are
not inferred from free text.

`GET /api/v1/warning-histories/{history_id}`

Returns the exact local identity, identity status, lifecycle status, all
deduplicated versions, and the chronological event timeline. It remains
available after a warning disappears from the current cache. A missing
`history_id` returns `404`.

Both responses include IMGW-PIB attribution, the MeteoLens processed-data
notice, the official-warning disclaimer, and an explicit prospective-history
boundary. Empty filtered feeds return the standard `empty_state`. Partial
snapshots and ambiguous identities remain visible; fetch/parser errors and
`404` source responses do not manufacture empty snapshots.

## Location Summary

`GET /api/v1/location/summary`

Query parameters:

- `lat`: required.
- `lon`: required.
- `radius_km`: optional, default 50.

Returns nearest stations, latest observations, and active warnings relevant to
the location. Station matching uses distance from cached point coordinates.
Warnings are returned as active cached warning records, with a note that exact
location matching is not available until area geometry datasets are cached.

The response includes `generated_at`, `cache`, and `empty_state` metadata like
other collection endpoints.

Stage 9 added spatial warning matching for this endpoint when reviewed
TERYT or basin geometries exist. The response distinguishes exact polygon
matches (`match_type: "polygon"`), fallback active-warning summaries, and
unresolved geometry via `notes`.

## Exports

`GET /api/v1/export/station/{id}.csv`

`GET /api/v1/export/station/{id}.json`

`GET /api/v1/export/station/{id}/observations.csv`

`GET /api/v1/export/station/{id}/observations.json`

`GET /api/v1/export/map.geojson`

`GET /api/v1/export/warnings.geojson`

`GET /api/v1/export/warning-events.csv`

`GET /api/v1/export/warning-events.json`

`GET /api/v1/export/map-state.json`

Export query parameters mirror the related station, observations, warning, and
map filters. Every export includes attribution, processed-data notice when
relevant, generated timestamp, retrieval timestamp where applicable, and
missing-field or missing-geometry metadata.

Warning-event exports accept the same `type`, `level`, `area`, `change_kind`,
`from`, `to`, `phenomenon`, and `office` filters as the feed. Their bounded
export limit is 1-5000, default 1000. They include uncertain and ambiguous
events rather than silently omitting them. JSON retains the structured event
payload; CSV includes stable event/history ids, change categories, changed
fields, classification basis, confidence, source identity, affected area
codes, `history_started_at`, attribution, processed notice, and disclaimer.

Station CSV columns:

- `station_id`
- `station_name`
- `metric`
- `value`
- `unit`
- `observed_at`
- `retrieved_at`
- `data_delay_seconds`
- `missing`
- `raw_field`
- `source_key`
- `attribution`
- `processed_notice`
- `missing_fields`

Station observation range exports support:

- `metric`
- `from`
- `to`
- `interval`: `raw`, `10m`, `1h`, or `1d`
- `limit`: maximum 5000

Observation CSV columns:

- `station_id`
- `station_name`
- `metric`
- `value`
- `unit`
- `observed_at`
- `retrieved_at`
- `data_delay_seconds`
- `missing`
- `raw_field`
- `origin`
- `import_run_id`
- `import_source_url`
- `source_station_id`
- `station_mapping_status`
- `station_mapping_version`
- `station_mapping_source_url`
- `station_mapping_retrieved_at`
- `archive_kind`
- `quality_status`
- `missing_reason`
- `temporal_resolution`
- `source_file_sha256`
- `source_file_last_modified`
- `source_key`
- `attribution`
- `processed_notice`
- `series_kind`
- `interval`

Map GeoJSON includes point station features plus foreign members for
`non_spatial_records`, `missing_geometry`, `cache`, `attribution`,
`geometry_attributions`, `processed_notice`, and `generated_at`.
`geometry_attributions` lists reviewed geometry dataset attribution strings
used by exported features, for example PRG/GUGiK attribution for warning
polygons or reviewed station-coordinate sources.

Warning GeoJSON supports the same warning filters as `/api/v1/warnings`, plus
`bbox`. It returns polygon features when reviewed geometry exists and keeps
warnings with unresolved geometry in `non_spatial_records` and
`missing_geometry`; absence of polygons is not treated as absence of warnings.

Map state JSON records the visible layer keys, optional map center/zoom/bbox,
mode, theme, current selection, warning filters, timeline selection, cache
state, and per-layer feature/record/missing-geometry counts. It is intended for
automation, troubleshooting, and reproducible power-user views, not as a
replacement for GeoJSON data exports.

Report-like PDF exports are not implemented. The optional future plan is in
[`docs/power-user/PDF_EXPORT_PLAN.md`](docs/power-user/PDF_EXPORT_PLAN.md).

## Raw Expert Data

No raw expert-data endpoint is currently supported. Raw source snippets are
included inside station and warning detail payloads where feasible. A future
`/api/v1/raw/...` endpoint may be added only if it preserves attribution,
missing-field metadata, and clear cache provenance.

## Product And Timeline APIs

Stage 10 exposed product classification and frame metadata; Stage 14 added the
first real rendering path (COSMO `*_00` 2 m temperature as a PNG map overlay).
Radar composites stay metadata-only (`rendering_status: download_blocked`)
because IMGW does not currently serve their files publicly.

### `GET /api/v1/products`

Returns IMGW product manifest entries enriched with research classification:

- `category`, `availability`, `rendering_status`, `high_value`, `format_notes`
- `rendering_status` values include `renderable` (COSMO `*_00`),
  `parser_not_implemented`, `download_blocked` (radar composites),
  `unsupported_format`, `unavailable`
- `research_date` (currently `2026-07-05`)
- `missing_fields` (source fields IMGW omitted, e.g. `id`/`url`/`opis`)
- per-product `source` metadata and attribution/processed notice at collection level
- `retrieved_at` is `null` when the product manifest cache is empty (never synthesized)

### `GET /api/v1/products/{product_id}/frames`

Query parameters: `limit` (1-500, default 120), `offset` (default 0).

Returns cached product detail manifest slices with parsed frame metadata:

- `frame_time`, `run_time` (model run for GRIB products), `frame_kind`
  (`forecast_lead`, `observation`, `preview`, `metadata`, `constant`),
  `missing`, `rendering_status`
- aggregate `frame_count`, `missing_frames`, `stale`, `retrieved_at`
- `renderable` — descriptor object for renderable products, otherwise `null`:
  `variables` (key/title/unit/legend), `default_variable`, `bounds`
  (west/south/east/north), `image_coordinates` (MapLibre TL/TR/BR/BL corners),
  `render_url_template`, `max_lead_hours`, `lead_step_hours`, `grid_note`,
  `attribution`, `processed_notice`
- per-frame render state on renderable products: `renderable` (bool),
  `renderable_reason` (`constant_field_file`, `not_a_forecast_frame`,
  `lead_beyond_render_window`, `lead_not_on_render_step`), and — for
  renderable frames — `render_url` and `render_ready` (PNG already cached)
- `empty_state.code` may be `cache_empty`, `product_unavailable`, or `frame_missing`

### `GET /api/v1/products/{product_id}/render/{filename}?variable=t2m`

Serves the rendered PNG overlay for one renderable frame (`image/png`). The
first request downloads the source GRIB server-side (can take seconds to tens
of seconds; downloads are serialized), then the cached PNG is served.

Public deployment note: this endpoint is expensive. Production nginx applies a
route-specific rate limit, while the backend bounds concurrent renders and
coalesces identical in-flight work so anonymous traffic cannot multiply large
downloads or CPU-heavy renders.

- Response headers: `X-MeteoLens-Frame-Time`, `X-MeteoLens-Run-Time`,
  `X-MeteoLens-Retrieved-At`, `X-MeteoLens-Rendered-At`, `X-MeteoLens-Variable`
- The PNG embeds attribution, the processed-data notice, and timing metadata
  as iTXt chunks; a JSON metadata sidecar backs `render_ready`
- Errors (`detail.error.code`): `not_renderable` (404), `frame_not_renderable`
  (404), `cache_empty` (503), `frame_missing` (404 — also used when IMGW
  returns an HTML page instead of a GRIB file), `download_blocked` (502),
  `download_failed` (502), `file_too_large` (502), `grid_mismatch` (502 —
  the file stopped matching the reviewed COSMO grid; rendering is refused
  rather than drawn at a wrong position), `variable_missing` (502)

### `GET /api/v1/map/timeline`

Returns time-aware layers derived from cached product detail manifests. Each layer
includes:

- `first_frame_time`, `last_frame_time`, `source_time`
- `frames_renderable` — `true` only when frames actually render as a map layer
- `renderable` — same descriptor as on the frames endpoint (or `null`)
- `stale`, `missing_frames`, attribution, processed notice, and explanatory `notes`

### Planned tile endpoint

Tile pyramids are not implemented. A future contract may add:

- `GET /api/v1/tiles/{product_id}/{z}/{x}/{y}`

Product and frame responses must label source time, frame time, missing frames,
stale frames, parser/rendering status, attribution, and processed-data notice.
Stable, unstable, missing, or risky product IDs must be visible in source
metadata. See [`docs/products/PRODUCT_RESEARCH.md`](docs/products/PRODUCT_RESEARCH.md).

## Power-User And Freshness APIs

Stage 11 added operational dashboards and comparison helpers. Saved locations,
views, dashboards, and local alert rules remain browser-local unless a future
authenticated backend is introduced.

### `GET /api/v1/status/freshness`

Returns aggregate cache freshness for all configured IMGW sources:

- `overall_status`: `healthy`, `stale`, `degraded`, or `empty`
- per-source `cache_status`, `age_seconds`, `ttl_seconds`, `stale`, parser warnings
- `alerting_disclaimer` clarifying MeteoLens is not an official alerting system

### `GET /api/v1/compare/warning-station/{station_id}`

Compares cached station observations with active warnings matched to the station
coordinates (when available). Includes `notes`, attribution, processed notice, and
the same alerting disclaimer.

Local alert evaluation in the UI uses live API data plus browser-stored rules; it
does not call a separate alerting endpoint.

See also:

- [`docs/pwa/PWA_PLAN.md`](docs/pwa/PWA_PLAN.md)
- [`docs/power-user/TREND_ANOMALY_IDEAS.md`](docs/power-user/TREND_ANOMALY_IDEAS.md)
- [`docs/power-user/OPENAPI_CLIENT.md`](docs/power-user/OPENAPI_CLIENT.md)

## SDK And Examples

The Stage 16 TypeScript client lives in
`packages/meteolens-api-client/`. It provides typed helpers for common
integration workflows:

- list stations,
- fetch station observations,
- build station range export URLs,
- check source freshness,
- fetch active warnings for a location,
- build warning GeoJSON export URLs.

The generated OpenAPI metadata file is committed so docs and tests can detect
drift from backend routes. Regenerate it after API changes:

```bash
backend/.venv/bin/python scripts/api/generate_ts_client.py
```

Runnable Node examples live under `examples/api/` and use
`METEOLENS_API_BASE_URL` to target local or deployed instances.

## Planned Power-User APIs

Future authenticated deployments may add server-side persistence for saved views
and alert delivery audit logs. Local alert endpoints must state that MeteoLens is
not an official alerting system and must not obscure IMGW-PIB warning responsibility.

## Error Shape

```json
{
  "error": {
    "code": "source_unavailable",
    "message": "IMGW-PIB source could not be fetched.",
    "source_key": "hydro",
    "retrieved_at": "2026-06-29T21:10:00Z",
    "retry_after_seconds": 300
  }
}
```

Planned error codes:

- `source_unavailable`,
- `source_timeout`,
- `parser_failed`,
- `cache_empty`,
- `cache_invalid`,
- `not_found`,
- `unsupported_layer`,
- `invalid_filter`.
- `geometry_unavailable`,
- `product_unavailable`,
- `frame_missing`,
- `alert_rule_invalid`.

Empty-state codes for collection responses:

- `no_matching_records`,
- `no_observations`,
- `no_location_data`.
