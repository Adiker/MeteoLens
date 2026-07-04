"""Convert PRG administrative-boundary shapefiles to reviewed MeteoLens GeoJSON.

Input: the PRG-derived voivodeship/county shapefiles published by GIS Support
(EPSG:2180, attributes JPT_KOD_JE = TERYT code, JPT_NAZWA_ = unit name):

    https://www.gis-support.pl/downloads/2022/wojewodztwa.zip
    https://www.gis-support.pl/downloads/2022/powiaty.zip

Canonical source: Państwowy Rejestr Granic (PRG), © GUGiK. See
docs/geometry/GEOMETRY_SOURCES.md for the source/legal review.

Output: simplified WGS84 GeoJSON files ready for the geometry import CLI:

    python scripts/geometry/convert_prg_shapefiles.py \
        --voivodeships-shp wojewodztwa/wojewodztwa.shp \
        --counties-shp powiaty/powiaty.shp \
        --out-dir out/

    cd backend
    python -m app.geometry.import_cli import teryt_voivodeships \
        ../out/teryt_voivodeships.geojson \
        --metadata ../docs/geometry/metadata/teryt_voivodeships.json
    python -m app.geometry.import_cli import teryt_counties \
        ../out/teryt_counties.geojson \
        --metadata ../docs/geometry/metadata/teryt_counties.json

Requires: pip install pyshp pyproj

Simplification uses Douglas-Peucker per ring (default 500 m for
voivodeships, 200 m for counties, in EPSG:2180 metres), so the output is
processed data: neighbouring units can show small slivers/gaps and the
geometry is not suitable for legal or cadastral use.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import shapefile
from pyproj import Transformer

TRANSFORMER = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def perpendicular_distance(
    point: list[float], start: list[float], end: list[float]
) -> float:
    x0, y0 = point
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
    t = ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    px, py = x1 + t * dx, y1 + t * dy
    return ((x0 - px) ** 2 + (y0 - py) ** 2) ** 0.5


def douglas_peucker(points: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue
        max_dist, max_index = 0.0, None
        for i in range(start + 1, end):
            dist = perpendicular_distance(points[i], points[start], points[end])
            if dist > max_dist:
                max_dist, max_index = dist, i
        if max_dist > tolerance and max_index is not None:
            keep[max_index] = True
            stack.append((start, max_index))
            stack.append((max_index, end))
    return [point for point, kept in zip(points, keep) if kept]


def simplify_ring(ring: list[list[float]], tolerance: float) -> list[list[float]] | None:
    closed = ring[0] == ring[-1]
    points = ring[:-1] if closed else ring[:]
    if len(points) < 4:
        return None
    # Split the ring in half so Douglas-Peucker has two fixed anchors.
    half = len(points) // 2
    part1 = douglas_peucker(points[: half + 1], tolerance)
    part2 = douglas_peucker(points[half:] + [points[0]], tolerance)
    simplified = part1[:-1] + part2[:-1]
    if len(simplified) < 4:
        return None
    simplified.append(simplified[0])
    return simplified


def transform_ring(ring: list[list[float]]) -> list[list[float]]:
    lons, lats = TRANSFORMER.transform(
        [point[0] for point in ring], [point[1] for point in ring]
    )
    return [[round(lon, 5), round(lat, 5)] for lon, lat in zip(lons, lats)]


def convert(shp_path: Path, out_path: Path, tolerance: float, props_builder) -> None:
    reader = shapefile.Reader(str(shp_path), encoding="utf-8")
    field_names = [field[0] for field in reader.fields[1:]]
    features = []
    for shape_record in reader.iterShapeRecords():
        record = dict(zip(field_names, list(shape_record.record)))
        geo = shape_record.shape.__geo_interface__
        if geo["type"] == "Polygon":
            polygons = [geo["coordinates"]]
        elif geo["type"] == "MultiPolygon":
            polygons = list(geo["coordinates"])
        else:
            raise ValueError(f"unexpected geometry {geo['type']}")
        out_polygons = []
        for polygon in polygons:
            out_rings = []
            for index, ring in enumerate(polygon):
                simplified = simplify_ring([list(point) for point in ring], tolerance)
                if simplified is None:
                    if index == 0:
                        # Never drop an exterior ring; keep it unsimplified.
                        simplified = [list(point) for point in ring]
                    else:
                        # A hole that collapses below the tolerance is dropped.
                        continue
                out_rings.append(transform_ring(simplified))
            if out_rings:
                out_polygons.append(out_rings)
        if not out_polygons:
            raise ValueError(f"feature {record.get('JPT_KOD_JE')} lost all geometry")
        geometry = (
            {"type": "Polygon", "coordinates": out_polygons[0]}
            if len(out_polygons) == 1
            else {"type": "MultiPolygon", "coordinates": out_polygons}
        )
        features.append(
            {
                "type": "Feature",
                "properties": props_builder(record),
                "geometry": geometry,
            }
        )
    features.sort(key=lambda feature: feature["properties"]["teryt"])
    collection = {"type": "FeatureCollection", "features": features}
    out_path.write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"{out_path}: {len(features)} features")


def voivodeship_props(record: dict) -> dict:
    code = record["JPT_KOD_JE"].strip()
    return {"teryt": code, "name": record["JPT_NAZWA_"].strip(), "province_code": code}


def county_props(record: dict) -> dict:
    code = record["JPT_KOD_JE"].strip()
    return {
        "teryt": code,
        "name": record["JPT_NAZWA_"].strip(),
        "county_code": code,
        "province_code": code[:2],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--voivodeships-shp", type=Path)
    parser.add_argument("--counties-shp", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    parser.add_argument("--voivodeships-tolerance", type=float, default=500.0)
    parser.add_argument("--counties-tolerance", type=float, default=200.0)
    args = parser.parse_args()
    if not args.voivodeships_shp and not args.counties_shp:
        parser.error("pass --voivodeships-shp and/or --counties-shp")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.voivodeships_shp:
        convert(
            args.voivodeships_shp,
            args.out_dir / "teryt_voivodeships.geojson",
            args.voivodeships_tolerance,
            voivodeship_props,
        )
    if args.counties_shp:
        convert(
            args.counties_shp,
            args.out_dir / "teryt_counties.geojson",
            args.counties_tolerance,
            county_props,
        )


if __name__ == "__main__":
    main()
