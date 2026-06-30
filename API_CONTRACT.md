# API_CONTRACT.md - MeteoLens Backend API Draft

Base path: `/api/v1`.

This is the frontend-facing API contract target. It may change during Stage 4,
but every public change must update this file.

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
If a later refresh fails after a previous successful refresh, the cache keeps
the last successful raw and normalized payload and reports the new error in
cache status.

This endpoint is operational tooling for MVP development. Scheduled refresh and
frontend-safe map/station/warning endpoints come in Stage 4.

## Map Layers

`GET /api/v1/map/layers`

Query parameters:

- `layers`: comma-separated layer keys.
- `bbox`: optional `minLon,minLat,maxLon,maxLat`.
- `time`: optional ISO timestamp for time-aware layers.
- `expert`: optional boolean for extra metadata.

Returns GeoJSON FeatureCollections grouped by layer:

```json
{
  "layers": [
    {
      "key": "hydro_stations",
      "title": "Stacje hydrologiczne",
      "source": {},
      "geojson": {
        "type": "FeatureCollection",
        "features": []
      }
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

`GET /api/v1/stations/{id}`

Returns station metadata, latest observations, source metadata, and raw metadata
availability.

`GET /api/v1/stations/{id}/observations`

Query parameters:

- `metric`: optional metric key.
- `from`: optional ISO timestamp.
- `to`: optional ISO timestamp.

Returns time-series values for charts and exports.

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

## Location Summary

`GET /api/v1/location/summary`

Query parameters:

- `lat`: required.
- `lon`: required.
- `radius_km`: optional, default 50.

Returns nearest stations, latest observations, and active warnings relevant to
the location.

## Exports

`GET /api/v1/export/station/{id}.csv`

`GET /api/v1/export/station/{id}.json`

`GET /api/v1/export/map.geojson`

Export query parameters mirror station/map filters. Every export must include
attribution, processed-data notice when relevant, generated timestamp, retrieval
timestamp, and missing-field metadata.

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
