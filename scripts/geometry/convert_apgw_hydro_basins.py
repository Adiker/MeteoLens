"""Build reviewed hydro_basins GeoJSON from II aPGW JCWP catchments.

IMGW ``kod_zlewni`` values follow ``{type}_{office}_{voivodeship}_{mphp_core}``
(e.g. ``Z_P_WP_1856``). The trailing numeric core matches the hierarchical
MPHP hydrographic identifier embedded in II aPGW JCWP codes
(``RW{dorzecze}{typ}{hydro_id}``).

Coverage strategy:

1. Exact / child / parent MPHP-core match against river JCWP catchments.
2. When the candidate union is too coarse (short core or too many JCWP),
   refine by warning-name token overlap and optional voivodeship intersection.
3. Coastal / lagoon warnings (core ``0`` or coastal names) map to reviewed
   CW/TW water-body polygons by curated name rules.

Source: II aktualizacja planów gospodarowania wodami (aPGW / IIaPGW),
PGW Wody Polskie, CC BY 4.0 on dane.gov.pl dataset 599. See
``docs/geometry/GEOMETRY_SOURCES.md``.

Requires: shapely
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

# IMGW cores that use a neighbouring MPHP id in the II aPGW JCWP embedding.
CORE_ALIASES: dict[str, str] = {
    "266": "267",
    "2664": "26714",
    "26636": "26714",
}

# Curated coastal / lagoon warning-name fragments → CW/TW MS_KOD values.
COASTAL_NAME_RULES: list[tuple[str, list[str]]] = [
    ("zalew wislany", ["TW20001WB1"]),
    ("zalew szczecinski", ["TW60001WB2"]),
    ("zalew kamienski", ["TW60001WB3"]),
    (
        "wybrzeze wschodnie",
        [
            "CW20001WB1",
            "CW20001WB2",
            "TW20002WB4",
            "TW20003WB5",
            "TW20004WB6",
            "TW20005WB7",
        ],
    ),
    (
        "baltyk poludniowo-wschodni",
        [
            "CW20001WB1",
            "CW20001WB2",
            "TW20002WB4",
            "TW20003WB5",
            "TW20004WB6",
            "TW20005WB7",
        ],
    ),
    (
        "wybrzeze zachodnie",
        ["CW60001WB3", "CW60001WB4", "TW60001WB2", "TW60001WB3"],
    ),
    (
        "baltyk poludniowy",
        ["CW60001WB3", "CW60001WB4", "TW60001WB2", "TW60001WB3"],
    ),
]

VOIVODESHIP_NAME_TO_TERYT = {
    "dolnośląskie": "02",
    "kujawsko-pomorskie": "04",
    "lubelskie": "06",
    "lubuskie": "08",
    "łódzkie": "10",
    "małopolskie": "12",
    "mazowieckie": "14",
    "opolskie": "16",
    "podkarpackie": "18",
    "podlaskie": "20",
    "pomorskie": "22",
    "śląskie": "24",
    "świętokrzyskie": "26",
    "warmińsko-mazurskie": "28",
    "wielkopolskie": "30",
    "zachodniopomorskie": "32",
}

STOP_TOKENS = frozenset(
    {
        "od",
        "do",
        "z",
        "ze",
        "i",
        "wraz",
        "ujscia",
        "ujscie",
        "zb",
        "zbiornika",
        "zbiornik",
        "zlewnia",
        "zlewnie",
        "zlewniami",
        "zlewnią",
        "przyrzecze",
        "doplywow",
        "doplywy",
        "glownie",
        "lewostronnych",
        "prawostronnych",
        "rz",
        "oraz",
        "na",
        "w",
        "po",
        "przy",
        "morskie",
        "wody",
        "wewnetrzne",
        "rp",
    }
)

JCWP_HYDRO_RE = re.compile(r"^(RW|LW)(\d{2})(\d{4})(\d+)$")
KOD_ZLEWNI_RE = re.compile(r"^([ZRW])_([A-Z])_([A-Z]{2})_(.+)$")


def fold(text: str) -> str:
    """Casefold and strip diacritics, including Polish-specific letters."""
    translated = text.casefold().translate(
        str.maketrans("ąćęłńóśźż", "acelnoszz")
    )
    normalized = unicodedata.normalize("NFKD", translated)
    return "".join(char for char in normalized if not unicodedata.combining(char))


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


def name_tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    folded = fold(text)
    tokens = re.findall(r"[a-z0-9]+", folded)
    return {token for token in tokens if len(token) > 2 and token not in STOP_TOKENS}


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


def load_jcwp_layers(paths: list[Path]) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, str],
    dict[str, dict[str, Any]],
]:
    """Index river hydro ids and absolute MS_KOD → feature for coastal bodies."""
    by_hydro: dict[str, list[dict[str, Any]]] = defaultdict(list)
    names: dict[str, str] = {}
    by_ms_kod: dict[str, dict[str, Any]] = {}

    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for feature in payload.get("features") or []:
            props = feature.get("properties") or {}
            if not feature.get("geometry"):
                continue
            kod = str(
                props.get("MS_KOD")
                or props.get("kod_jcwp")
                or props.get("code")
                or ""
            ).strip()
            if not kod:
                continue
            label = (
                props.get("Nazwa_JCWP")
                or props.get("nazwa_jcwp")
                or props.get("name")
            )
            if label:
                names[kod] = str(label)
                hydro = extract_hydro_id(kod)
                if hydro:
                    names[hydro] = str(label)
            by_ms_kod[kod] = feature
            hydro = extract_hydro_id(kod)
            if hydro is not None:
                by_hydro[hydro].append(feature)
    return by_hydro, names, by_ms_kod


def load_voivodeship_geometries(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    geometries: dict[str, Any] = {}
    for feature in payload.get("features") or []:
        props = feature.get("properties") or {}
        teryt = str(props.get("teryt") or props.get("code") or "").strip()
        if not teryt or not feature.get("geometry"):
            continue
        geom = shape(feature["geometry"])
        if not geom.is_valid:
            geom = geom.buffer(0)
        geometries[teryt] = geom
    return geometries


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
        method = "children" if mapped == core else f"alias_children:{mapped}"
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


def score_name_overlap(warning_name: str | None, jcwp_name: str | None) -> float:
    warning_tokens = name_tokens(warning_name)
    jcwp_tokens = name_tokens(jcwp_name)
    if not warning_tokens or not jcwp_tokens:
        return 0.0
    overlap = warning_tokens & jcwp_tokens
    if not overlap:
        return 0.0
    return len(overlap) / len(warning_tokens)


def refine_hydro_ids_by_name(
    hydro_ids: list[str],
    *,
    warning_name: str | None,
    hydro_names: dict[str, str],
    min_score: float = 0.34,
) -> list[str]:
    if not warning_name or not hydro_ids:
        return hydro_ids
    scored = [
        (score_name_overlap(warning_name, hydro_names.get(hydro)), hydro)
        for hydro in hydro_ids
    ]
    kept = sorted(hydro for score, hydro in scored if score >= min_score)
    if kept:
        return kept
    # Fall back to any positive overlap if the threshold filtered everything.
    kept = sorted(hydro for score, hydro in scored if score > 0)
    return kept or hydro_ids


def dissolve_features(features: list[dict[str, Any]]) -> Any | None:
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
            geom
            for geom in dissolved.geoms
            if geom.geom_type in {"Polygon", "MultiPolygon"}
        ]
        if not polygons:
            return None
        dissolved = unary_union(polygons)
    return dissolved


def geometry_to_geojson(geom: Any, *, simplify: float = 0.012) -> dict[str, Any] | None:
    if geom is None or geom.is_empty:
        return None
    simplified = geom.simplify(simplify, preserve_topology=True)
    if simplified.is_empty:
        return None
    mapped = mapping(simplified)
    mapped["coordinates"] = round_coords(mapped["coordinates"])
    return mapped


def intersect_voivodeship(
    geom: Any,
    *,
    voivodeship_name: str | None,
    voivodeship_geoms: dict[str, Any],
) -> tuple[Any, str | None]:
    if geom is None or not voivodeship_name:
        return geom, None
    teryt = VOIVODESHIP_NAME_TO_TERYT.get(voivodeship_name.casefold())
    if teryt is None:
        teryt = VOIVODESHIP_NAME_TO_TERYT.get(fold(voivodeship_name))
    # Also try exact keys with diacritics preserved via casefold map above.
    if teryt is None:
        for name, code in VOIVODESHIP_NAME_TO_TERYT.items():
            if fold(name) == fold(voivodeship_name):
                teryt = code
                break
    if teryt is None or teryt not in voivodeship_geoms:
        return geom, None
    clipped = geom.intersection(voivodeship_geoms[teryt])
    if clipped.is_empty:
        return geom, None
    return clipped, teryt


def coastal_ms_kods(warning_name: str | None) -> list[str]:
    if not warning_name:
        return []
    folded_name = fold(warning_name)
    for fragment, codes in COASTAL_NAME_RULES:
        if fragment in folded_name:
            return list(codes)
    return []


def build_hydro_basins(
    *,
    jcwp_geojsons: list[Path],
    warnings_json: Path,
    char_csv: Path | None = None,
    voivodeships_geojson: Path | None = None,
    min_core_length: int = 3,
    max_jcwp_count: int = 80,
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_hydro, hydro_names, by_ms_kod = load_jcwp_layers(jcwp_geojsons)
    if char_csv is not None and char_csv.exists():
        for row in csv.DictReader(char_csv.open(encoding="utf-8")):
            kod = row.get("kod_jcwp") or ""
            name = row.get("nazwa_jcwp")
            if not name:
                continue
            hydro_names[kod] = name
            hydro = extract_hydro_id(kod)
            if hydro:
                hydro_names[hydro] = name

    voivodeship_geoms = load_voivodeship_geometries(voivodeships_geojson)
    warning_codes = load_warning_codes(warnings_json)
    dissolved_cache: dict[tuple[str, ...], dict[str, Any]] = {}
    groups: dict[tuple[str, ...], dict[str, Any]] = {}
    coverage: dict[str, Any] = {
        "warning_code_count": len(warning_codes),
        "resolved_codes": [],
        "unresolved_codes": [],
        "methods": defaultdict(int),
        "min_core_length": min_core_length,
        "max_jcwp_count": max_jcwp_count,
    }

    def register(
        *,
        code: str,
        core: str | None,
        name: str | None,
        method: str,
        feature_keys: list[str],
        source_features: list[dict[str, Any]],
        voivodeship: str | None,
        precision: str,
    ) -> bool:
        if not source_features:
            return False
        cache_key = tuple(
            [
                "geom",
                *sorted(feature_keys),
                precision,
                voivodeship if precision in {"coarse", "refined"} else "",
            ]
        )
        geometry = dissolved_cache.get(cache_key)
        method_local = method
        if geometry is None:
            dissolved = dissolve_features(source_features)
            if dissolved is None:
                return False
            if voivodeship and precision in {"coarse", "refined"}:
                clipped, teryt = intersect_voivodeship(
                    dissolved,
                    voivodeship_name=voivodeship,
                    voivodeship_geoms=voivodeship_geoms,
                )
                if (
                    teryt is not None
                    and clipped is not None
                    and not clipped.is_empty
                    and clipped.area < dissolved.area * 0.98
                ):
                    dissolved = clipped
                    method_local = f"{method}+voiv_clip"
            geometry = geometry_to_geojson(dissolved)
            if geometry is None:
                return False
            dissolved_cache[cache_key] = geometry

        group = groups.get(cache_key)
        if group is None:
            group = {
                "codes": [],
                "core": core,
                "method": method_local,
                "jcwp_count": len(feature_keys),
                "name": name or f"zlewnia {core or code}",
                "geometry": geometry,
                "precision": precision,
            }
            groups[cache_key] = group
        group["codes"].append(code)
        if name and group["name"].startswith("zlewnia "):
            group["name"] = name

        coverage["resolved_codes"].append(
            {
                "code": code,
                "core": core,
                "name": group["name"],
                "method": method_local,
                "jcwp_count": len(feature_keys),
                "precision": precision,
            }
        )
        coverage["methods"][method_local.split(":")[0].split("+")[0]] += 1
        return True

    for code in sorted(warning_codes):
        info = warning_codes[code]
        warning_name = info.get("name")
        voivodeship = info.get("voivodeship")
        core = extract_mphp_core(code)

        # 1) Coastal / lagoon curated mapping.
        coastal_codes = coastal_ms_kods(warning_name)
        if coastal_codes:
            features = [by_ms_kod[ms] for ms in coastal_codes if ms in by_ms_kod]
            if register(
                code=code,
                core=core,
                name=warning_name,
                method="coastal_name",
                feature_keys=coastal_codes,
                source_features=features,
                voivodeship=None,
                precision="coastal",
            ):
                continue

        # 2) MPHP-core match (skip empty/zero cores — try name search below).
        hydro_ids: list[str] = []
        method = "unresolved"
        if core not in {None, "0"}:
            assert core is not None
            hydro_ids, method = match_hydro_ids(core, by_hydro)

        if not hydro_ids:
            name_hits = [
                key
                for key, label in hydro_names.items()
                if (key in by_hydro or key in by_ms_kod)
                and score_name_overlap(warning_name, label) >= 0.5
            ]
            if name_hits:
                hydro_ids = sorted(set(name_hits))
                method = "name_search"
            else:
                coverage["unresolved_codes"].append(
                    {
                        "code": code,
                        "core": core,
                        "name": warning_name,
                        "reason": "no_jcwp_match",
                    }
                )
                continue

        needs_refine = (
            core in {None, "0"}
            or (core is not None and len(core) < min_core_length)
            or len(hydro_ids) > max_jcwp_count
        )
        precision = "standard"
        if needs_refine:
            refined = refine_hydro_ids_by_name(
                hydro_ids,
                warning_name=warning_name,
                hydro_names=hydro_names,
            )
            if refined != hydro_ids:
                hydro_ids = refined
                method = f"{method}+name_refine"
            if len(hydro_ids) > max_jcwp_count:
                precision = "coarse"
                method = f"{method}+coarse"
            else:
                precision = "refined"

        source_features: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        for key in hydro_ids:
            for feature in by_hydro.get(key, []):
                feature_id = id(feature)
                if feature_id not in seen_ids:
                    source_features.append(feature)
                    seen_ids.add(feature_id)
            feature = by_ms_kod.get(key)
            if feature is not None and id(feature) not in seen_ids:
                source_features.append(feature)
                seen_ids.add(id(feature))

        if not register(
            code=code,
            core=core,
            name=warning_name,
            method=method,
            feature_keys=hydro_ids,
            source_features=source_features,
            voivodeship=voivodeship,
            precision=precision,
        ):
            coverage["unresolved_codes"].append(
                {
                    "code": code,
                    "core": core,
                    "name": warning_name,
                    "reason": "empty_geometry",
                }
            )

    features: list[dict[str, Any]] = []
    for group in groups.values():
        codes = sorted(set(group["codes"]))
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
                    "mapping_precision": group["precision"],
                    "jcwp_count": group["jcwp_count"],
                    "kod_zlewni_codes": codes,
                },
                "geometry": group["geometry"],
            }
        )
    features.sort(key=lambda feature: feature["properties"]["code"])

    collection = {"type": "FeatureCollection", "features": features}
    coverage["resolved_count"] = len(coverage["resolved_codes"])
    coverage["unresolved_count"] = len(coverage["unresolved_codes"])
    coverage["methods"] = dict(coverage["methods"])
    coverage["unique_geometries"] = len(groups)
    coverage["feature_count"] = len(features)
    precision_counts: dict[str, int] = defaultdict(int)
    for item in coverage["resolved_codes"]:
        precision_counts[item["precision"]] += 1
    coverage["precision_counts"] = dict(precision_counts)
    return collection, coverage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--jcwp-geojson",
        type=Path,
        nargs="+",
        required=True,
        help="One or more simplified JCWP GeoJSON layers (river + coastal).",
    )
    parser.add_argument("--warnings-json", type=Path, required=True)
    parser.add_argument("--char-csv", type=Path, default=None)
    parser.add_argument("--voivodeships-geojson", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--coverage-out", type=Path, default=None)
    parser.add_argument("--min-core-length", type=int, default=3)
    parser.add_argument("--max-jcwp-count", type=int, default=80)
    args = parser.parse_args()

    collection, coverage = build_hydro_basins(
        jcwp_geojsons=list(args.jcwp_geojson),
        warnings_json=args.warnings_json,
        char_csv=args.char_csv,
        voivodeships_geojson=args.voivodeships_geojson,
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
        f"{args.out}: resolved {coverage['resolved_count']}/"
        f"{coverage['warning_code_count']}; "
        f"unresolved {coverage['unresolved_count']}; "
        f"features {coverage['feature_count']}; "
        f"{args.out.stat().st_size // 1024} KiB"
    )
    print("precision", coverage["precision_counts"])
    print(f"coverage report: {coverage_path}")


if __name__ == "__main__":
    main()
