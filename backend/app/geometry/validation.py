"""Validation for reviewed geometry datasets before they are used.

Every dataset must pass these checks before the import CLI installs it into
the geometry cache, and the loader re-runs the structural checks defensively
at startup. Coverage checks (`strict_coverage=True`) run only at import time
so that small test fixtures stay loadable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Poland bounding box with a small margin. WGS84 / EPSG:4326.
POLAND_LON_MIN = 13.5
POLAND_LAT_MIN = 48.5
POLAND_LON_MAX = 24.5
POLAND_LAT_MAX = 55.5

# Official two-digit TERYT voivodeship codes (even numbers 02..32).
VOIVODESHIP_TERYT_CODES = frozenset(f"{value:02d}" for value in range(2, 33, 2))

POLYGONAL_TYPES = frozenset({"Polygon", "MultiPolygon"})
POINT_TYPES = frozenset({"Point"})

CODE_PROPERTIES = ("teryt", "code", "basin_code", "TERYT", "id")
NAME_PROPERTIES = ("name", "nazwa", "label")

MAX_REPORTED_ISSUES = 50


@dataclass(frozen=True)
class DatasetRules:
    allowed_geometry_types: frozenset[str]
    code_pattern: str | None
    description: str


DATASET_RULES: dict[str, DatasetRules] = {
    "teryt_voivodeships": DatasetRules(
        allowed_geometry_types=POLYGONAL_TYPES,
        code_pattern=r"^\d{2}$",
        description="TERYT voivodeship polygons",
    ),
    "teryt_counties": DatasetRules(
        allowed_geometry_types=POLYGONAL_TYPES,
        code_pattern=r"^\d{4}$",
        description="TERYT county polygons",
    ),
    "hydro_basins": DatasetRules(
        allowed_geometry_types=POLYGONAL_TYPES,
        # IMGW kod_zlewni: {Z|R|W}_{office}_{voivodeship}_{mphp_core}[_{suffix}]
        code_pattern=r"^[ZRW]_[A-Z]_[A-Z]{2}_.+$",
        description="Hydrological basin polygons",
    ),
    "synop_stations": DatasetRules(
        allowed_geometry_types=POINT_TYPES,
        code_pattern=r"^\d+$",
        description="Synoptic station coordinates",
    ),
}

GENERIC_RULES = DatasetRules(
    allowed_geometry_types=POLYGONAL_TYPES | POINT_TYPES,
    code_pattern=r"^\S+$",
    description="Generic reviewed geometry dataset",
)


@dataclass
class ValidationReport:
    dataset_key: str
    feature_count: int = 0
    codes: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def add_issue(self, message: str) -> None:
        if len(self.issues) < MAX_REPORTED_ISSUES:
            self.issues.append(message)
        elif len(self.issues) == MAX_REPORTED_ISSUES:
            self.issues.append("Further issues truncated.")


def rules_for_dataset(dataset_key: str) -> DatasetRules:
    return DATASET_RULES.get(dataset_key, GENERIC_RULES)


def validate_dataset(
    dataset_key: str,
    payload: Any,
    *,
    strict_coverage: bool = False,
) -> ValidationReport:
    report = ValidationReport(dataset_key=dataset_key)
    rules = rules_for_dataset(dataset_key)

    if not isinstance(payload, dict):
        report.add_issue("Payload is not a JSON object.")
        return report
    if payload.get("type") != "FeatureCollection":
        report.add_issue("Payload is not a GeoJSON FeatureCollection.")
        return report
    features = payload.get("features")
    if not isinstance(features, list):
        report.add_issue("FeatureCollection has no features list.")
        return report
    if not features:
        report.add_issue("FeatureCollection contains no features.")
        return report

    seen_codes: set[str] = set()
    for index, feature in enumerate(features):
        prefix = f"Feature {index}"
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            report.add_issue(f"{prefix}: not a GeoJSON Feature object.")
            continue

        properties = feature.get("properties")
        if not isinstance(properties, dict):
            report.add_issue(f"{prefix}: missing properties object.")
            properties = {}

        code = _extract_code(properties)
        if code is None:
            report.add_issue(
                f"{prefix}: no identifier property (expected one of {CODE_PROPERTIES})."
            )
        else:
            prefix = f"Feature {index} ({code})"
            if rules.code_pattern and not re.match(rules.code_pattern, code):
                report.add_issue(
                    f"{prefix}: identifier does not match pattern {rules.code_pattern!r}."
                )
            if code in seen_codes:
                report.add_issue(f"{prefix}: duplicate identifier.")
            else:
                seen_codes.add(code)
                report.codes.append(code)

        if _extract_name(properties) is None:
            report.add_issue(f"{prefix}: no name property (expected one of {NAME_PROPERTIES}).")

        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            report.add_issue(f"{prefix}: missing geometry object.")
            continue
        geometry_type = geometry.get("type")
        if geometry_type not in rules.allowed_geometry_types:
            report.add_issue(
                f"{prefix}: geometry type {geometry_type!r} not allowed for "
                f"{dataset_key} (expected {sorted(rules.allowed_geometry_types)})."
            )
            continue
        report.feature_count += 1
        _validate_coordinates(geometry_type, geometry.get("coordinates"), prefix, report)

    if dataset_key == "teryt_counties":
        _validate_county_prefixes(report)
    if strict_coverage:
        _validate_coverage(dataset_key, report)

    return report


def _extract_code(properties: dict[str, Any]) -> str | None:
    for key in CODE_PROPERTIES:
        value = properties.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return None


def _extract_name(properties: dict[str, Any]) -> str | None:
    for key in NAME_PROPERTIES:
        value = properties.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _validate_coordinates(
    geometry_type: str,
    coordinates: Any,
    prefix: str,
    report: ValidationReport,
) -> None:
    if coordinates is None:
        report.add_issue(f"{prefix}: geometry has no coordinates.")
        return
    if geometry_type == "Point":
        _validate_position(coordinates, prefix, report)
        return
    if geometry_type == "Polygon":
        _validate_polygon(coordinates, prefix, report)
        return
    if geometry_type == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            report.add_issue(f"{prefix}: MultiPolygon has no polygons.")
            return
        for polygon in coordinates:
            _validate_polygon(polygon, prefix, report)


def _validate_polygon(polygon: Any, prefix: str, report: ValidationReport) -> None:
    if not isinstance(polygon, list) or not polygon:
        report.add_issue(f"{prefix}: polygon has no rings.")
        return
    for ring in polygon:
        if not isinstance(ring, list) or len(ring) < 4:
            report.add_issue(f"{prefix}: polygon ring has fewer than 4 positions.")
            continue
        if ring[0] != ring[-1]:
            report.add_issue(f"{prefix}: polygon ring is not closed.")
        for position in ring:
            if not _validate_position(position, prefix, report):
                break


def _validate_position(position: Any, prefix: str, report: ValidationReport) -> bool:
    if (
        not isinstance(position, list)
        or len(position) < 2
        or not all(isinstance(value, int | float) for value in position[:2])
    ):
        report.add_issue(f"{prefix}: malformed coordinate position.")
        return False
    lon, lat = float(position[0]), float(position[1])
    if not (POLAND_LON_MIN <= lon <= POLAND_LON_MAX and POLAND_LAT_MIN <= lat <= POLAND_LAT_MAX):
        report.add_issue(
            f"{prefix}: coordinate ({lon}, {lat}) outside Poland bounds "
            f"(lon {POLAND_LON_MIN}..{POLAND_LON_MAX}, lat {POLAND_LAT_MIN}..{POLAND_LAT_MAX})."
        )
        return False
    return True


def _validate_county_prefixes(report: ValidationReport) -> None:
    for code in report.codes:
        if len(code) == 4 and code[:2] not in VOIVODESHIP_TERYT_CODES:
            report.add_issue(
                f"County code {code}: prefix {code[:2]!r} is not a TERYT voivodeship code."
            )


def _validate_coverage(dataset_key: str, report: ValidationReport) -> None:
    codes = set(report.codes)
    if dataset_key == "teryt_voivodeships":
        missing = sorted(VOIVODESHIP_TERYT_CODES - codes)
        if missing:
            report.add_issue(f"Missing voivodeship codes: {', '.join(missing)}.")
        unexpected = sorted(codes - VOIVODESHIP_TERYT_CODES)
        if unexpected:
            report.add_issue(f"Unexpected voivodeship codes: {', '.join(unexpected)}.")
    elif dataset_key == "teryt_counties":
        prefixes = {code[:2] for code in codes if len(code) == 4}
        missing = sorted(VOIVODESHIP_TERYT_CODES - prefixes)
        if missing:
            report.add_issue(
                f"No county coverage for voivodeship codes: {', '.join(missing)}."
            )
    elif not codes:
        report.add_issue("Dataset has no usable identifiers.")
