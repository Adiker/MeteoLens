# GEOMETRY_SOURCES.md - Reviewed Geometry Datasets

MeteoLens renders IMGW warning areas and station markers only from **reviewed**
geometry datasets cached under `data/geometry/`. Stage 9 added the loader and
spatial matching; Stage 13 added the reviewed-manifest format, the import CLI,
strict validation, and the first two implemented datasets (PRG voivodeships and
counties).

## Source And Legal Review Checklist

For each candidate dataset document:

- provider and canonical URL,
- license/terms URL and attribution text,
- whether public and commercial use are allowed,
- caching, redistribution, screenshot, and export implications,
- dataset version or publication date and update cadence,
- geometry format and coordinate reference system (expected: WGS84 / EPSG:4326),
- code system and mapping key (TERYT, basin code, station ID),
- known gaps and unresolved mapping behaviour,
- implementation status: `planned`, `implemented`, `risky`, or `blocked`.

Do not ship unofficial or legally unclear geometry as an implemented source.

## Dataset Status Overview

| Dataset key | Purpose | Source | Status |
| --- | --- | --- | --- |
| `teryt_voivodeships` | Voivodeship polygons, meteo warning fallback, province filter | PRG (GUGiK) via GIS Support SHP mirror | **implemented** |
| `teryt_counties` | County polygons for meteo warning TERYT codes, county filter | PRG (GUGiK) via GIS Support SHP mirror | **implemented** |
| `hydro_basins` | Hydro warning basin polygons, basin filters | MPHP (PGW Wody Polskie) — candidate | planned (licensing and `kod_zlewni` mapping unverified) |
| `synop_stations` | Synoptic station coordinates (IMGW synop API has none) | WMO OSCAR/Surface, resolved by WIGOS ID from IMGW `id_stacji` | **implemented** |

## Implemented: `teryt_voivodeships` and `teryt_counties`

- **Provider:** Główny Urząd Geodezji i Kartografii (GUGiK) — Państwowy Rejestr
  Granic (PRG). Converted SHP copies downloaded from GIS Support:
  `https://www.gis-support.pl/downloads/2022/wojewodztwa.zip` and
  `https://www.gis-support.pl/downloads/2022/powiaty.zip` (PRG snapshot,
  `WERSJA_OD` 2022, EPSG:2180, attributes `JPT_KOD_JE` = TERYT,
  `JPT_NAZWA_` = name).
- **Canonical URL:**
  <https://www.gugik.gov.pl/pzgik/dane-bez-oplat/dane-z-panstwowego-rejestru-granic-i-powierzchni-jednostek-podzialow-terytorialnych-kraju-prg>
- **License/terms:** PRG unit-of-territorial-division boundary data is free
  public data under art. 40a ust. 2 pkt 1 of the Polish Geodetic and
  Cartographic Law (Prawo geodezyjne i kartograficzne). Terms overview:
  <https://www.gugik.gov.pl/pzgik/dane-bez-oplat>.
- **Public use:** allowed. **Commercial use:** allowed.
- **Attribution text:** `Granice administracyjne: Państwowy Rejestr Granic
  (PRG), © GUGiK; kopia SHP: gis-support.pl; uproszczenie geometrii:
  MeteoLens.`
- **Caching/redistribution/screenshot/export implications:** local caching and
  redistribution of PRG-derived boundaries are allowed with source attribution.
  The committed GeoJSON files are **simplified derivatives** (processed data);
  screenshots and exports that show warning polygons must keep the IMGW-PIB
  attribution plus the processed-data notice, and expert mode exposes the
  geometry attribution via `/api/v1/geometry/datasets`.
- **Update cadence:** PRG is updated continuously by GUGiK; the imported
  snapshot is from 2022. Refresh by downloading a newer PRG export, re-running
  the conversion script, and re-importing.
- **Known limitations:** geometry is simplified with Douglas-Peucker
  (tolerance 500 m for voivodeships, 200 m for counties), so hairline
  slivers/gaps between neighbouring units can occur; administrative boundary
  changes after the 2022 snapshot are not reflected; not suitable for legal or
  cadastral use.

Reproducible pipeline:

```bash
# 1. download and unzip the PRG-derived shapefiles listed above
# 2. convert + reproject + simplify (requires: pip install pyshp pyproj)
python scripts/geometry/convert_prg_shapefiles.py \
  --voivodeships-shp wojewodztwa/wojewodztwa.shp \
  --counties-shp powiaty/powiaty.shp --out-dir out/

# 3. validate + install with the documented review metadata
cd backend
python -m app.geometry.import_cli import teryt_voivodeships \
  ../out/teryt_voivodeships.geojson \
  --metadata ../docs/geometry/metadata/teryt_voivodeships.json
python -m app.geometry.import_cli import teryt_counties \
  ../out/teryt_counties.geojson \
  --metadata ../docs/geometry/metadata/teryt_counties.json
```

Conversion sanity checks performed for the committed import: feature counts
(16 voivodeships, 380 counties), full TERYT coverage of all 16 voivodeship
codes, Poland coordinate bounds, and point-in-polygon checks for Warszawa,
Kraków, Gdańsk, Wrocław, Białystok, Suwałki, and powiat tatrzański. All TERYT
codes from live `warningsmeteo` responses resolved against the county dataset
at import time.

## Candidate: `hydro_basins` (planned)

- **Candidate provider:** PGW Wody Polskie — Mapa Podziału Hydrograficznego
  Polski (MPHP), e.g. via <https://dane.gov.pl>.
- **Open questions before implementation:** exact license/terms for
  redistribution of MPHP geometry; mapping between IMGW `kod_zlewni` values
  (e.g. `Z_P_WP_1856`) and MPHP basin identifiers; dataset size and
  simplification strategy.
- Until reviewed, hydro warnings stay list-only with
  `missing_area_geometry_dataset` / `geometry_not_found` metadata.

## Implemented: `synop_stations`

- IMGW's synop API returns no coordinates, and the public station list
  (`https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/wykaz_stacji.csv`)
  contains station codes and names but **no coordinates**, so it cannot be the
  coordinate source on its own.
- **Provider:** World Meteorological Organization (WMO) OSCAR/Surface
  (<https://oscar.wmo.int/surface/>), cross-referenced with the current IMGW
  SYNOP endpoint. WMO describes OSCAR as its global repository of
  observing-system capabilities, and WMO wis2box documentation identifies
  OSCAR/Surface as the key station-metadata resource and documents fetching and
  caching station metadata by WIGOS ID.
- **Mapping key:** Polish synoptic stations use WMO block 12 identifiers that
  match IMGW `id_stacji`; WIGOS IDs use `0-20000-0-<id_stacji>`, e.g.
  `0-20000-0-12295` for Białystok.
- **License/terms:** reviewed against WMO Unified Data Policy Resolution 1 and
  WMO OSCAR/Surface station-metadata caching guidance. Public use and local
  redistribution are treated as allowed with attribution. MeteoLens does not
  assert commercial-use clearance for this dataset; commercial deployments must
  re-review current WMO/OSCAR terms.
- **Attribution text:** `Współrzędne stacji synoptycznych: WMO OSCAR/Surface;
  identyfikatory stacji i dane pomiarowe: IMGW-PIB; przetworzenie:
  MeteoLens.`
- **Update cadence:** manual reviewed refresh. Re-run
  `scripts/geometry/fetch_oscar_synop_stations.py`, then import with
  `python -m app.geometry.import_cli import synop_stations ...`.
- **Known limitations:** committed import covers the 62 stations present in the
  live IMGW SYNOP endpoint during the 2026-07-07 refresh. OSCAR station
  metadata can change independently of IMGW observation rows; coordinates are
  not legal/cadastral positions.

Reproducible pipeline:

```bash
python scripts/geometry/fetch_oscar_synop_stations.py \
  --out out/synop_stations.geojson
cd backend
python -m app.geometry.import_cli import synop_stations \
  ../out/synop_stations.geojson \
  --metadata ../docs/geometry/metadata/synop_stations.json
```

Stage 18 verification resolved all 62 current IMGW SYNOP station IDs through
OSCAR WIGOS IDs and imported the reviewed Point dataset into `data/geometry/`.
Synop stations now render as map markers with visible `coordinate_source`
metadata; unresolved future stations still remain explicit as
`missing_lat_lon`.

## Manifest Format (format_version 2)

`data/geometry/manifest.json` lists reviewed datasets. Every entry must carry
full provenance and an approved review, otherwise the loader refuses it with a
`dataset_not_reviewed` error (visible in `/api/v1/geometry/datasets`):

```json
{
  "format_version": 2,
  "datasets": [
    {
      "key": "teryt_counties",
      "file": "teryt_counties.geojson",
      "title": "Powiaty – granice administracyjne (PRG)",
      "provider": "GUGiK – Państwowy Rejestr Granic (PRG)",
      "canonical_url": "https://www.gugik.gov.pl/pzgik/dane-bez-oplat/...",
      "license_url": "https://www.gugik.gov.pl/pzgik/dane-bez-oplat",
      "license_note": "Free public data under art. 40a ust. 2 pkt 1 ...",
      "attribution": "Granice administracyjne: PRG, © GUGiK; ...",
      "public_use": true,
      "commercial_use": true,
      "redistribution_note": "Allowed with attribution; simplified derivative.",
      "update_cadence": "PRG continuous; imported snapshot 2022.",
      "known_limitations": "Simplified geometry; 2022 snapshot.",
      "dataset_version": "PRG WERSJA_OD 2022; MeteoLens simplification 2026-07-04",
      "imported_at": "2026-07-04T14:20:00+00:00",
      "feature_count": 380,
      "review": {
        "status": "approved",
        "reviewed_at": "2026-07-04",
        "reviewed_by": "MeteoLens Stage 13 source/legal review",
        "notes": "..."
      }
    }
  ]
}
```

Do not edit `manifest.json` by hand; use the import CLI so validation always
runs. Reference metadata files live under `docs/geometry/metadata/`.

## Import CLI And Validation

```bash
cd backend
python -m app.geometry.import_cli validate <dataset-key> <file.geojson>
python -m app.geometry.import_cli import <dataset-key> <file.geojson> \
  --metadata <metadata.json> [--geometry-dir DIR]
python -m app.geometry.import_cli status
```

Validation (strict at import time, structural re-check at load time):

- GeoJSON syntax: FeatureCollection with Feature objects,
- geometry types per dataset (`Polygon`/`MultiPolygon` for areas, `Point` for
  stations), closed rings with at least 4 positions,
- required properties: an identifier (`teryt`/`code`/`basin_code`) and a name,
- identifier patterns (2-digit voivodeship TERYT, 4-digit county TERYT with a
  valid voivodeship prefix, numeric station IDs) and duplicate detection,
- coordinate bounds for Poland (lon 13.5–24.5, lat 48.5–55.5, WGS84),
- coverage at import time: all 16 voivodeship codes present; counties cover
  every voivodeship prefix.

## Mapping Rules

- Meteo warnings: IMGW `teryt` codes map to `teryt_counties` first, then
  `teryt_voivodeships` when the code itself is a two-digit voivodeship code.
- Hydro warnings: IMGW `kod_zlewni` values map to `hydro_basins`.
- Synop stations: IMGW `id_stacji` maps to `synop_stations` Point features
  resolved from WMO OSCAR/Surface by WIGOS ID.
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
