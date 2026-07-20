"""Build reviewed hydro_basins GeoJSON from II aPGW JCWP catchments.

IMGW ``kod_zlewni`` values follow ``{type}_{office}_{voivodeship}_{mphp_core}``
(e.g. ``Z_P_WP_1856``). The trailing numeric core matches the hierarchical
MPHP hydrographic identifier embedded in II aPGW JCWP codes
(``RW{dorzecze}{typ}{hydro_id}``).

This script:

1. loads simplified JCWP catchment polygons (EPSG:4326 GeoJSON from aPGW),
2. extracts the embedded hydro id from each ``MS_KOD`` / ``kod_jcwp``,
3. maps live or snapshotted IMGW ``kod_zlewni`` values onto those catchments,
5. dissolves matching catchments into unique geometries,
6. emits one Feature per unique dissolved geometry with ``code`` /
   ``basin_code`` set to a primary IMGW identifier and ``kod_zlewni_codes``
   listing every alias that shares that catchment so the loader resolves them.

Source: II aktualizacja planów gospodarowania wodami (aPGW / IIaPGW),
PGW Wody Polskie, CC BY 4.0 on dane.gov.pl dataset 599. See
``docs/geometry/GEOMETRY_SOURCES.md``.

Example:

```bash
# 1. download aPGW GDB from dane.gov.pl resource 53330 and simplify:
docker run --rm -v "$PWD/apgw:/data" -v "$PWD/out:/out" \\
  ghcr.io/osgeo/gdal:ubuntu-small-latest \\
  ogr2ogr -f GeoJSON /out/zlewnie_jcwp_rzecznych.geojson \\
  /data/Geobaza_2aPGW_ver_20230915.gdb Zlewnie_JCWP_rzecznych \\
  -t_srs EPSG:4326 -simplify 400 -lco COORDINATE_PRECISION=5 \\
  -select MS_KOD,AREA

# 2. map + dissolve
python scripts/geometry/convert_apgw_hydro_basins.py \\
  --jcwp-geojson out/zlewnie_jcwp_rzecznych.geojson \\
  --warnings-json out/warningshydro_snapshot.json \\
  --out out/hydro_basins.geojson

# 3. import
cd backend
python -m app.geometry.import_cli import hydro_basins \\
  ../out/hydro_basins.geojson \\
  --metadata ../docs/geometry/metadata/hydro_basins.json
```

Requires: shapely
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

# IMGW cores that use a neighbouring MPHP id in the II aPGW JCWP embedding.
# Bug catchments are coded 266* by IMGW warnings but 267* in aPGW JCWP.
CORE_ALIASES: dict[str, str] = {
    "266": "267",
    "2664": "26714",
    "26636": "26714",
}

JCWP_HYDRO_RE = re.compile(r"^(RW|LW|CW|TW)(\d{2})(\d{4})(\d+)$")
KOD_ZLEWNI_RE = re.compile(r"^([ZRW])_([A-Z])_([A-Z]{2})_(.+)$")


def extract_hydro_id(kod_jcwp: str) -> str | None:
    match = JCWP_HYDRO_RE.match(kod_jcwp.strip())
    if match is None:
        return None
    return match.group(4)


def extract_mphp_core(kod_zlewni: str) -> str | None:
    match = KOD_ZLEWNI_RE.match(kod_zlewni.strip())
    if match is None:
        return None
    local = match.group(4)
    return re.sub(r"(_[A-Z])+$", "", local)


def basin_name_from_opis(opis: str | None) -> str | None:
    if not opis:
        return None
    parts = [part.strip() for part in opis.split(",")]
    if len(parts) >= 2:
        return parts[1] or None
    return opis.strip() or None


def round_coords(obj: Any, ndigits: int = 5) -> Any:
    if isinstance(obj, (float, int)):
        return round(float(obj), ndigits)
    if isinstance(obj, list):
        return [round_coords(item, ndigits) for item in obj]
    return obj


def load_warning_codes(path: Path) -> dict[str, dict[str, str | None]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    codes: dict[str, dict[str, str | None]] = {}
    for warning in payload:
        for area in warning.get("obszary") or []:
            name = basin_name_from_opis(area.get("opis"))
            voivodeship = area.get("wojewodztwo")
            for code in area.get("kod_zlewni") or []:
                if not isinstance(code, str) or not code.strip():
                    continue
                codes[code.strip()] = {
                    "name": name,
                    "voivodeship": voivodeship,
                }
    return codes


def index_jcwp_features(
    geojson_path: Path,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    payload = json.loads(geojson_path.read_text(encoding="utf-8"))
    by_hydro: dict[str, list[dict[str, Any]]] = defaultdict(list)
    names: dict[str, str] = {}
    for feature in payload.get("features") or []:
        props = feature.get("properties") or {}
        kod = str(props.get("MS_KOD") or props.get("kod_jcwp") or "").strip()
        hydro = extract_hydro_id(kod)
        if hydro is None or not feature.get("geometry"):
            continue
        by_hydro[hydro].append(feature)
        label = props.get("nazwa_jcwp") or props.get("name")
        if label:
            names[hydro] = str(label)
    return by_hydro, names


def match_hydro_ids(
    core: str,
    by_hydro: dict[str, list[dict[str, Any]]],
) -> tuple[list[str], str]:
    mapped = CORE_ALIASES.get(core, core)
    if mapped in by_hydro:
        return [mapped], "exact" if mapped == core else f"alias:{mapped}"

    children = sorted(
        hydro for hydro in by_hydro if hydro.startswith(mapped) and hydro != mapped
    )
    if children:
        method = "children"
        if mapped != core:
            method = f"alias_children:{mapped}"
        return children, method

    parents = sorted(
        (
            hydro
            for hydro in by_hydro
            if mapped.startswith(hydro) and hydro != mapped
        ),
        key=len,
        reverse=True,
    )
    if parents:
        method = f"parent:{parents[0]}"
        if mapped != core:
            method = f"alias_parent:{parents[0]}"
        return [parents[0]], method
    return [], "unresolved"


def dissolve_features(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    geometries = []
    for feature in features:
        try:
            geom = shape(feature["geometry"])
        except Exception:
            continue
        if geom.is_empty:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
        if not geom.is_empty:
            geometries.append(geom)
    if not geometries:
        return None
    dissolved = unary_union(geometries)
    if dissolved.is_empty:
        return None
    if dissolved.geom_type == "GeometryCollection":
        polygons = [
            geom for geom in dissolved.geoms if geom.geom_type in {"Polygon", "MultiPolygon"}
        ]
        if not polygons:
            return None
        dissolved = unary_union(polygons)
    geo = mapping(dissolved)
    geo["coordinates"] = round_coords(geo["coordinates"])
    return geo


def build_hydro_basins(
    *,
    jcwp_geojson: Path,
    warnings_json: Path,
    char_csv: Path | None = None,
    min_core_length: int = 3,
    max_jcwp_count: int = 80,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build one Feature per IMGW ``kod_zlewni`` with dissolved JCWP geometry.

    Short MPHP cores (``1``, ``2``, ``18``) would dissolve into whole river-basin
    trees and are rejected unless they stay under ``max_jcwp_count``. Those codes
    remain explicitly unresolved so list-only fallback stays honest.
    """
    by_hydro, hydro_names = index_jcwp_features(jcwp_geojson)
    if char_csv is not None and char_csv.exists():
        import csv

        for row in csv.DictReader(char_csv.open(encoding="utf-8")):
            hydro = extract_hydro_id(row.get("kod_jcwp") or "")
            name = row.get("nazwa_jcwp")
            if hydro and name:
                hydro_names[hydro] = name

    warning_codes = load_warning_codes(warnings_json)
    dissolved_cache: dict[tuple[str, ...], dict[str, Any]] = {}
    # Group IMGW codes by the dissolved JCWP set they resolve to.
    groups: dict[tuple[str, ...], dict[str, Any]] = {}
    coverage = {
        "warning_code_count": len(warning_codes),
        "resolved_codes": [],
        "unresolved_codes": [],
        "methods": defaultdict(int),
        "min_core_length": min_core_length,
        "max_jcwp_count": max_jcwp_count,
    }

    for code in sorted(warning_codes):
        info = warning_codes[code]
        core = extract_mphp_core(code)
        if core is None or core == "0":
            coverage["unresolved_codes"].append(
                {"code": code, "core": core, "name": info.get("name"), "reason": "no_mphp_core"}
            )
            continue
        if len(core) < min_core_length:
            coverage["unresolved_codes"].append(
                {
                    "code": code,
                    "core": core,
                    "name": info.get("name"),
                    "reason": "core_too_coarse",
                }
            )
            continue

        hydro_ids, method = match_hydro_ids(core, by_hydro)
        if not hydro_ids:
            coverage["unresolved_codes"].append(
                {
                    "code": code,
                    "core": core,
                    "name": info.get("name"),
                    "reason": "no_jcwp_match",
                }
            )
            continue
        if len(hydro_ids) > max_jcwp_count:
            coverage["unresolved_codes"].append(
                {
                    "code": code,
                    "core": core,
                    "name": info.get("name"),
                    "reason": "jcwp_union_too_large",
                    "jcwp_count": len(hydro_ids),
                }
            )
            continue

        cache_key = tuple(hydro_ids)
        geometry = dissolved_cache.get(cache_key)
        if geometry is None:
            source_features = [
                feature for hydro in hydro_ids for feature in by_hydro.get(hydro, [])
            ]
            geometry = dissolve_features(source_features)
            if geometry is None:
                coverage["unresolved_codes"].append(
                    {
                        "code": code,
                        "core": core,
                        "name": info.get("name"),
                        "reason": "empty_geometry",
                    }
                )
                continue
            geom = shape(geometry).simplify(0.012, preserve_topology=True)
            mapped = mapping(geom)
            mapped["coordinates"] = round_coords(mapped["coordinates"])
            geometry = mapped
            dissolved_cache[cache_key] = geometry

        group = groups.get(cache_key)
        if group is None:
            name = info.get("name") or hydro_names.get(hydro_ids[0]) or f"zlewnia {core}"
            group = {
                "codes": [],
                "core": core,
                "method": method,
                "jcwp_count": len(hydro_ids),
                "name": name,
                "geometry": geometry,
            }
            groups[cache_key] = group
        group["codes"].append(code)
        if info.get("name") and not group["name"]:
            group["name"] = info["name"]

        coverage["resolved_codes"].append(
            {
                "code": code,
                "core": core,
                "name": group["name"],
                "method": method,
                "jcwp_count": len(hydro_ids),
            }
        )
        coverage["methods"][method.split(":")[0]] += 1

    features: list[dict[str, Any]] = []
    for group in groups.values():
        codes = sorted(group["codes"])
        # Primary code is the first IMGW identifier; aliases keep every other
        # kod_zlewni that shares this dissolved catchment discoverable.
        primary = codes[0]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "code": primary,
                    "basin_code": primary,
                    "name": group["name"],
                    "mphp_core": group["core"],
                    "mapping_method": group["method"],
                    "jcwp_count": group["jcwp_count"],
                    "kod_zlewni_codes": codes,
                },
                "geometry": group["geometry"],
            }
        )
    features.sort(key=lambda feature: feature["properties"]["code"])

    collection = {
        "type": "FeatureCollection",
        "features": features,
    }
    coverage["resolved_count"] = len(coverage["resolved_codes"])
    coverage["unresolved_count"] = len(coverage["unresolved_codes"])
    coverage["methods"] = dict(coverage["methods"])
    coverage["unique_geometries"] = len(groups)
    coverage["feature_count"] = len(features)
    return collection, coverage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jcwp-geojson", type=Path, required=True)
    parser.add_argument("--warnings-json", type=Path, required=True)
    parser.add_argument("--char-csv", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--coverage-out", type=Path, default=None)
    parser.add_argument("--min-core-length", type=int, default=3)
    parser.add_argument("--max-jcwp-count", type=int, default=80)
    args = parser.parse_args()

    collection, coverage = build_hydro_basins(
        jcwp_geojson=args.jcwp_geojson,
        warnings_json=args.warnings_json,
        char_csv=args.char_csv,
        min_core_length=args.min_core_length,
        max_jcwp_count=args.max_jcwp_count,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    coverage_path = args.coverage_out or args.out.with_suffix(".coverage.json")
    coverage_path.write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"{args.out}: {coverage['resolved_count']} features; "
        f"{coverage['unresolved_count']} unresolved; "
        f"{args.out.stat().st_size // 1024} KiB"
    )
    print(f"coverage report: {coverage_path}")


if __name__ == "__main__":
    main()
