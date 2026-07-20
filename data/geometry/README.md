# Reviewed geometry datasets

This directory holds reviewed geometry datasets and their `manifest.json`
(format_version 2). MeteoLens loads datasets only from this directory; it does
not download geometry automatically.

Shipped datasets:

- `teryt_voivodeships.geojson` — voivodeship boundaries, PRG © GUGiK
  (simplified derivative, processed data),
- `teryt_counties.geojson` — county boundaries, PRG © GUGiK (simplified
  derivative, processed data),
- `hydro_basins.geojson` — hydrological warning basin polygons derived from
  II aPGW JCWP catchments © PGW Wody Polskie (CC BY 4.0), mapped to IMGW
  `kod_zlewni` (simplified derivative, processed data; Stage 22),
- `synop_stations.geojson` — synoptic station coordinates from WMO
  OSCAR/Surface, resolved by WIGOS ID against the current IMGW SYNOP station
  list (processed metadata; Stage 18).

Do not edit `manifest.json` by hand. Import or update datasets with the CLI so
validation and review metadata stay consistent:

```bash
cd backend
python -m app.geometry.import_cli validate <dataset-key> <file.geojson>
python -m app.geometry.import_cli import <dataset-key> <file.geojson> \
  --metadata ../docs/geometry/metadata/<dataset-key>.json
python -m app.geometry.import_cli status
```

GeoJSON features must expose a stable `code` property (or `teryt` /
`basin_code`) matching IMGW warning area codes, plus a `name` property. Hydro
basins may also list alias IMGW codes in `kod_zlewni_codes`. Station datasets
(`synop_stations`) use Point features with `code` = IMGW `id_stacji`.

Refresh the bundled hydro basins with:

```bash
python scripts/geometry/convert_apgw_hydro_basins.py \
  --jcwp-geojson out/zlewnie_jcwp_rzecznych.geojson \
  --warnings-json out/warningshydro_snapshot.json \
  --out out/hydro_basins.geojson
cd backend
python -m app.geometry.import_cli import hydro_basins \
  ../out/hydro_basins.geojson \
  --metadata ../docs/geometry/metadata/hydro_basins.json
```

Refresh the bundled synop station coordinates with:

```bash
python scripts/geometry/fetch_oscar_synop_stations.py \
  --out out/synop_stations.geojson
cd backend
python -m app.geometry.import_cli import synop_stations \
  ../out/synop_stations.geojson \
  --metadata ../docs/geometry/metadata/synop_stations.json
```

See `docs/geometry/GEOMETRY_SOURCES.md` for the source/legal review of every
dataset and the full manifest format.
