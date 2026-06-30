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

`POST /api/v1/sources/{source_key}/refresh`

Fetches the public IMGW source, parses it, writes raw and normalized payloads to
the backend cache, and returns refresh metadata. Supported `source_key` values:
`synop`, `hydro`, `meteo`, `warningsmeteo`, `warningshydro`, `product`.

This endpoint is operational tooling for MVP development. Stage 4 frontend-safe
endpoints read from the normalized payloads written by this endpoint.

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
features only if coordinates exist; otherwise they are listed in
`missing_geometry`. Warning records do not yet have polygons and are returned in
`records` with area codes and `missing_area_geometry_dataset` metadata.

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
      "latest_observed_at": "2026-06-30T07:00:00+02:00",
      "data_delay_seconds": 1800,
      "missing_fields": ["temperatura_wody"],
      "source": {},
      "raw_available": true
    }
  ]
}
```

`GET /api/v1/stations/{id}`

Returns station metadata, latest observations, source metadata, and raw metadata
availability. IDs use the normalized stable form, for example
`synop:12295`, `hydro:151140030`, or `meteo:252210290`.

`GET /api/v1/stations/{id}/observations`

Query parameters:

- `metric`: optional metric key.
- `from`: optional ISO timestamp.
- `to`: optional ISO timestamp.

Returns time-series values for charts and exports.

Each observation preserves `null` values and includes `missing`,
`raw_field`, `observed_at`, `retrieved_at`-derived `data_delay_seconds`, and
unit metadata where available.

## Warnings

`GET /api/v1/warnings`

Query parameters:

- `type`: `meteo`, `hydro`.
- `active_at`: optional ISO timestamp.
- `level`: optional warning level.
- `phenomenon`: optional text/enum filter.
- `teryt`: optional administrative area code.
- `basin`: optional hydrological basin code.

`GET /api/v1/warnings/{id}`

Returns warning detail, affected areas, geometry references, source metadata, and
raw JSON availability.

Warnings currently expose `area_codes` from IMGW TERYT/basin/province metadata
and `geometry_status: "missing_area_geometry_dataset"` until TERYT and basin
geometry datasets are added.

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
`processed_notice`, and `generated_at`.

## Raw Expert Data

`GET /api/v1/raw/{source_key}/{source_id}`

Returns raw source payload slices when available. This endpoint is for expert
mode and debugging, not for primary UI rendering.

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
- `not_found`,
- `unsupported_layer`,
- `invalid_filter`.
