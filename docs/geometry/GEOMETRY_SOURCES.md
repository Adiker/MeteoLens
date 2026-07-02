# GEOMETRY_SOURCES.md - Reviewed Geometry Datasets

Stage 9 adds a local geometry cache under `data/geometry/`. Every dataset must
pass the legal/source review checklist before it is listed in `manifest.json`.

## Source And Legal Review Checklist

For each candidate dataset document:

- provider and canonical URL,
- dataset version or publication date,
- license/terms and attribution text,
- whether public and commercial use are allowed,
- update cadence and refresh process,
- geometry format and coordinate reference system (expected: WGS84 / EPSG:4326),
- code system and mapping key (TERYT, basin code, station ID),
- known gaps and unresolved mapping behaviour,
- implementation status: `planned`, `implemented`, `risky`, or `blocked`.

Do not ship unofficial or legally unclear geometry as an implemented source.

## Candidate Datasets

| Dataset key | Purpose | Candidate source | Status |
| --- | --- | --- | --- |
| `teryt_voivodeships` | Meteo warning voivodeship fallback | GUS TERYT / official administrative open data after legal review | planned |
| `teryt_counties` | Meteo warning county polygons, province/county filters | GUS TERYT / official administrative open data after legal review | planned |
| `hydro_basins` | Hydro warning basin polygons, basin filters | Public hydrological basin/catchment dataset after legal review | planned |
| `synop_stations` | Synoptic station coordinate reconciliation | Official IMGW or GUS station metadata after legal review | planned |

## Mapping Rules

- Meteo warnings: IMGW `teryt` codes map to `teryt_counties` first, then
  `teryt_voivodeships` by two-digit prefix.
- Hydro warnings: IMGW `kod_zlewni` values map to `hydro_basins`.
- Unresolved codes remain visible in API/UI as `geometry_not_found` or
  `missing_area_geometry_dataset`; MeteoLens must not hide partial data.

## Test Fixtures

Parser/API tests use tiny GeoJSON fixtures under
`backend/tests/fixtures/geometry/`. These are **test-only** and must not be used
in production deployments.

## Operational Notes

- Keep reviewed datasets in persistent storage alongside the IMGW cache.
- Document attribution for every geometry layer in deployment notes and expert UI.
- Re-run the legal review when a provider changes terms or dataset versioning.
