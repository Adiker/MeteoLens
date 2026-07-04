# API_CONTRACT.md - MeteoLens Backend API Draft

Base path: `/api/v1`.

This is the frontend-facing API contract. Stage 4 implements the map, station,
warning, location summary, and export endpoints from normalized cache records.

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

Returns service status and version.

```json
{
  "status": "ok",
  "service": "meteolens-backend",
  "version": "0.1.0"
}
```

## Sources

`GET /api/v1/sources`

Returns supported source descriptors, cache status, and parser status.

Stage 2 implementation returns planned descriptors only. Real cache freshness
and parser status will be wired during Stage 3.

Stage 3 implementation returns parser status and file-cache status for the
current IMGW sources.

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
features only when coordinates come from a reviewed `synop_stations` geometry
dataset; otherwise they are listed in `missing_geometry` with
`missing_lat_lon`. Warning areas are emitted as polygon features when their
TERYT/basin codes resolve against reviewed geometry datasets (Stage 13 ships
PRG voivodeship and county polygons); unresolved codes stay visible in
`records` and `missing_geometry` with `geometry_not_found` or
`missing_area_geometry_dataset` reasons.

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
- `interval`: planned Stage 8 aggregation interval such as `raw`, `10m`,
  `1h`, or `1d`.
- `limit`: planned Stage 8 maximum number of returned points.

Returns observation values for charts and exports. The implementation reads
persisted observation history when available and falls back to the latest cache
snapshot when history is empty. Responses include `series_kind` (`history` or
`snapshot`) and the requested `interval`.

Each observation preserves `null` values and includes `missing`,
`raw_field`, `observed_at`, `retrieved_at`, `data_delay_seconds`, and
unit metadata where available.

`GET /api/v1/stations/compare`

`GET /api/v1/rankings`

`GET /api/v1/export/station/{id}/observations.csv`

`GET /api/v1/export/station/{id}/observations.json`

Planned station comparison parameters:

- `station_ids`: comma-separated stable station IDs.
- `metric`: required metric key.
- `from`: optional ISO timestamp.
- `to`: optional ISO timestamp.
- `interval`: optional aggregation interval.
- `limit`: optional point limit.

Planned ranking parameters:

- `metric`: one of supported ranking metrics, for example temperature,
  wind speed, precipitation, or water level.
- `direction`: `highest` or `lowest` where applicable.
- `from`: optional ISO timestamp.
- `to`: optional ISO timestamp.
- `station_type`: optional station type filter.
- `limit`: optional result limit.

Stage 8 ranking responses must preserve source metadata, missing-field metadata,
and processed-data notices. Ranking logic must not replace missing values with
zero.

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

Warnings expose `area_codes` from IMGW TERYT/basin/province metadata. When
reviewed geometry datasets are cached under `METEOLENS_GEOMETRY_DIR`, map layers
and warning detail responses include resolved polygon GeoJSON plus
`unresolved_areas` for codes that cannot be mapped.

Stage 9 adds reviewed geometry references or GeoJSON features for warning
areas where code mapping is reliable. Responses continue to expose
unresolved codes and missing geometry reasons instead of hiding partial data.

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

Stage 9 adds spatial warning matching for this endpoint when reviewed
TERYT or basin geometries exist. The response distinguishes exact polygon
matches (`match_type: "polygon"`), fallback active-warning summaries, and
unresolved geometry via `notes`.

## Exports

`GET /api/v1/export/station/{id}.csv`

`GET /api/v1/export/station/{id}.json`

`GET /api/v1/export/map.geojson`

Export query parameters mirror station/map filters. Every export must include
attribution, processed-data notice when relevant, generated timestamp, retrieval
timestamp, and missing-field metadata.

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

Map GeoJSON includes point station features plus foreign members for
`non_spatial_records`, `missing_geometry`, `cache`, `attribution`,
`geometry_attributions`, `processed_notice`, and `generated_at`.
`geometry_attributions` lists reviewed geometry dataset attribution strings
used by exported features, for example PRG/GUGiK attribution for warning
polygons or reviewed station-coordinate sources.

## Raw Expert Data

`GET /api/v1/raw/{source_key}/{source_id}`

Returns raw source payload slices when available. This endpoint is for expert
mode and debugging, not for primary UI rendering.

## Product And Timeline APIs

Stage 10 exposes product classification and frame metadata only. Binary download,
parsing, and tile rendering remain deferred.

### `GET /api/v1/products`

Returns IMGW product manifest entries enriched with research classification:

- `category`, `availability`, `rendering_status`, `high_value`, `format_notes`
- `research_date` (currently `2026-07-01`)
- `missing_fields` (source fields IMGW omitted, e.g. `id`/`url`/`opis`)
- per-product `source` metadata and attribution/processed notice at collection level
- `retrieved_at` is `null` when the product manifest cache is empty (never synthesized)

### `GET /api/v1/products/{product_id}/frames`

Query parameters: `limit` (1-500, default 120), `offset` (default 0).

Returns cached product detail manifest slices with parsed frame metadata:

- `frame_time`, `frame_kind`, `missing`, `rendering_status`
- aggregate `frame_count`, `missing_frames`, `stale`, `retrieved_at`
- `empty_state.code` may be `cache_empty`, `product_unavailable`, or `frame_missing`

### `GET /api/v1/map/timeline`

Returns time-aware layers derived from cached product detail manifests. Each layer
includes:

- `first_frame_time`, `last_frame_time`, `source_time`
- `frames_renderable` (currently always `false`)
- `stale`, `missing_frames`, attribution, processed notice, and explanatory `notes`

### Planned tile endpoint

Binary rendering is not implemented. A future contract may add:

- `GET /api/v1/tiles/{product_id}/{z}/{x}/{y}`

Product and frame responses must label source time, frame time, missing frames,
stale frames, parser/rendering status, attribution, and processed-data notice.
Stable, unstable, missing, or risky product IDs must be visible in source
metadata. See [`docs/products/PRODUCT_RESEARCH.md`](docs/products/PRODUCT_RESEARCH.md).

## Power-User And Freshness APIs

Stage 11 adds operational dashboards and comparison helpers. Saved locations,
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
