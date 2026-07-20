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
| `hydro_basins` | Hydro warning basin polygons, basin filters | II aPGW JCWP catchments (PGW Wody Polskie) via dane.gov.pl dataset 599 | **implemented** |
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

## Implemented: `hydro_basins`

- **Provider:** Państwowe Gospodarstwo Wodne Wody Polskie (PGW WP) — II
  aktualizacja planów gospodarowania wodami (II aPGW / IIaPGW). Catchment
  polygons come from the `Zlewnie_JCWP_rzecznych` layer in the public
  Geobaza II aPGW package on dane.gov.pl dataset 599 (resource 53330), not
  from a direct MPHP redistribution.
- **Canonical URL:**
  <https://dane.gov.pl/pl/dataset/599,ii-aktualizacja-planow-gospodarowania-wodami>
- **License/terms:** Creative Commons Attribution 4.0 International (CC BY 4.0)
  on the published II aPGW spatial layers:
  <https://creativecommons.org/licenses/by/4.0/deed.pl>.
- **Public use:** allowed. **Commercial use:** allowed (with attribution).
- **Attribution text:** `Zlewnie JCWP: II aktualizacja planów gospodarowania
  wodami (aPGW), © PGW Wody Polskie (CC BY 4.0); mapowanie IMGW kod_zlewni i
  uproszczenie geometrii: MeteoLens.`
- **Mapping key:** IMGW `kod_zlewni` values follow
  `{Z|R|W}_{office}_{voivodeship}_{mphp_core}` (e.g. `Z_P_WP_1856`). The
  trailing numeric core matches the hierarchical MPHP hydrographic identifier
  embedded in II aPGW JCWP codes (`RW{dorzecze}{typ}{hydro_id}`). Matching
  JCWP catchments are dissolved per unique geometry; every IMGW code that
  shares that dissolve is listed in `kod_zlewni_codes` so the loader can
  resolve aliases.
- **Caching/redistribution/screenshot/export implications:** local caching and
  redistribution of this simplified derivative are allowed under CC BY 4.0 with
  PGW WP / II aPGW attribution plus the MeteoLens processed-data notice.
  Screenshots and exports that show hydro warning polygons must keep IMGW-PIB
  warning attribution as well. Expert mode exposes geometry attribution via
  `/api/v1/geometry/datasets`.
- **Update cadence:** re-export `Zlewnie_JCWP_rzecznych` from a newer II aPGW
  Geobaza, refresh a `warningshydro` snapshot, re-run
  `scripts/geometry/convert_apgw_hydro_basins.py`, and re-import.
- **Known limitations:** short MPHP cores (`len < 3`) and JCWP unions larger
  than 80 catchments stay explicitly unresolved to avoid whole-river-basin
  trees; coastal/sea codes with core `0` have no river JCWP match; geometry is
  further simplified (~0.012°) for map delivery; not for legal or flood-defence
  engineering use. Coverage summary:
  `docs/geometry/hydro_basins.coverage.json`.

Reproducible pipeline:

```bash
# 1. download II aPGW GDB from dane.gov.pl resource 53330 and simplify:
docker run --rm -v "$PWD/apgw:/data" -v "$PWD/out:/out" \
  ghcr.io/osgeo/gdal:ubuntu-small-latest \
  ogr2ogr -f GeoJSON /out/zlewnie_jcwp_rzecznych.geojson \
  /data/Geobaza_2aPGW_ver_20230915.gdb Zlewnie_JCWP_rzecznych \
  -t_srs EPSG:4326 -simplify 400 -lco COORDINATE_PRECISION=5 \
  -select MS_KOD,AREA

# 2. map + dissolve (requires: pip install shapely)
python scripts/geometry/convert_apgw_hydro_basins.py \
  --jcwp-geojson out/zlewnie_jcwp_rzecznych.geojson \
  --warnings-json out/warningshydro_snapshot.json \
  --out out/hydro_basins.geojson

# 3. import
cd backend
python -m app.geometry.import_cli import hydro_basins \
  ../out/hydro_basins.geojson \
  --metadata ../docs/geometry/metadata/hydro_basins.json
```

Conversion sanity checks for the committed import (2026-07-20 snapshot): 103
unique dissolved geometries covering 166 of 297 live `kod_zlewni` values;
131 unresolved (103 coarse cores, 22 oversized unions, 6 coastal/sea cores);
Poland coordinate bounds; loader alias resolution via `kod_zlewni_codes`.

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
  valid voivodeship prefix, IMGW `kod_zlewni` for hydro basins, numeric station
  IDs) and duplicate detection,
- coordinate bounds for Poland (lon 13.5–24.5, lat 48.5–55.5, WGS84),
- coverage at import time: all 16 voivodeship codes present; counties cover
  every voivodeship prefix.

## Mapping Rules

- Meteo warnings: IMGW `teryt` codes map to `teryt_counties` first, then
  `teryt_voivodeships` when the code itself is a two-digit voivodeship code.
- Hydro warnings: IMGW `kod_zlewni` values map to `hydro_basins` (primary
  `code`/`basin_code` or `kod_zlewni_codes` aliases). When the dataset is
  loaded but a code is unmatched, `geometry_status` is `geometry_not_found`
  rather than `missing_area_geometry_dataset`.
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
