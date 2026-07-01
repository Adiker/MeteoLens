"""Spatial matching helpers for reviewed geometry datasets."""

from __future__ import annotations

from typing import Any

from app.geometry.loader import GeometryFeature, GeometryStore
from app.normalization.models import Warning, WarningArea


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    if len(ring) < 3:
        return False
    inside = False
    j = len(ring) - 1
    for i, vertex in enumerate(ring):
        xi, yi = vertex[0], vertex[1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = (yi > lat) != (yj > lat) and lon < (
            (xj - xi) * (lat - yi) / (yj - yi + 0.0) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _point_in_polygon(lon: float, lat: float, polygon: list[list[list[float]]]) -> bool:
    if not polygon or not _point_in_ring(lon, lat, polygon[0]):
        return False
    return not any(_point_in_ring(lon, lat, hole) for hole in polygon[1:])


def point_in_geometry(lon: float, lat: float, feature: GeometryFeature) -> bool:
    geometry_type = feature.geometry_type
    coordinates = feature.coordinates
    if geometry_type == "Polygon" and coordinates:
        return _point_in_polygon(lon, lat, coordinates)
    if geometry_type == "MultiPolygon" and coordinates:
        return any(_point_in_polygon(lon, lat, polygon) for polygon in coordinates)
    return False


def _dataset_keys_for_area(area: WarningArea) -> list[str]:
    if area.area_type == "teryt":
        return ["teryt_counties", "teryt_voivodeships"]
    if area.area_type == "basin":
        return ["hydro_basins"]
    return []


def find_area_geometry(store: GeometryStore, area: WarningArea) -> GeometryFeature | None:
    if area.area_type == "teryt":
        feature = store.find_by_code(dataset_key="teryt_counties", code=area.code)
        if feature is not None:
            return feature
        if len(area.code) >= 2:
            return store.find_by_code(
                dataset_key="teryt_voivodeships",
                code=area.code[:2],
            )
        return None
    for dataset_key in _dataset_keys_for_area(area):
        feature = store.find_by_code(dataset_key=dataset_key, code=area.code)
        if feature is not None:
            return feature
    return None


def resolve_warning_geometries(
    warning: Warning,
    store: GeometryStore,
) -> dict[str, Any]:
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for area in warning.areas:
        feature = find_area_geometry(store, area)
        if feature is None:
            unresolved.append(
                {
                    "area_type": area.area_type,
                    "code": area.code,
                    "label": area.label,
                    "reason": "geometry_not_found",
                    "dataset_keys": _dataset_keys_for_area(area),
                }
            )
            continue

        resolved.append(
            {
                "area_type": area.area_type,
                "code": area.code,
                "label": feature.label or area.label,
                "geometry": {
                    "type": feature.geometry_type,
                    "coordinates": feature.coordinates,
                },
                "dataset_key": feature.dataset_key,
                "source_file": feature.source_file,
            }
        )

    if resolved:
        status = "partial" if unresolved else "resolved"
    elif store.datasets:
        status = "missing_area_geometry_dataset"
    else:
        status = "missing_area_geometry_dataset"

    return {
        "geometry_status": status,
        "resolved_areas": resolved,
        "unresolved_areas": unresolved,
        "geojson": _areas_to_feature_collection(warning, resolved),
    }


def warnings_matching_point(
    *,
    lat: float,
    lon: float,
    warnings: list[Warning],
    store: GeometryStore,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    polygon_matches: list[dict[str, Any]] = []
    fallback_active: list[dict[str, Any]] = []
    notes: list[str] = []

    for warning in warnings:
        geometry = resolve_warning_geometries(warning, store)
        matched = False
        for area in geometry["resolved_areas"]:
            feature = find_area_geometry(
                store,
                WarningArea(
                    area_type=area["area_type"],
                    code=area["code"],
                    label=area.get("label"),
                ),
            )
            if feature is None:
                continue
            if point_in_geometry(lon, lat, feature):
                payload = _warning_payload_with_geometry(warning, geometry)
                payload["match_type"] = "polygon"
                payload["matched_area"] = area
                polygon_matches.append(payload)
                matched = True
                break
        if not matched:
            fallback_active.append(_warning_payload_with_geometry(warning, geometry))

    if polygon_matches:
        notes.append(
            "Polygon-matched warnings use reviewed TERYT/basin geometry datasets."
        )
    elif fallback_active and store.datasets:
        notes.append(
            "No polygon-matched warnings for this location. Active warnings without "
            "exact geometry match are listed separately."
        )
    elif fallback_active:
        notes.append(
            "Warnings are not spatially matched yet because reviewed geometry datasets "
            "are not cached."
        )
    return polygon_matches, fallback_active, notes


def warning_matches_spatial_filters(
    warning: Warning,
    store: GeometryStore,
    *,
    province: str | None,
    county: str | None,
    basin: str | None,
) -> bool:
    if basin is not None and not any(
        area.area_type == "basin" and area.code == basin for area in warning.areas
    ):
        return False
    if county is not None and not any(
        area.area_type == "teryt" and area.code == county for area in warning.areas
    ):
        return False
    if province is not None:
        normalized = province.casefold()
        for area in warning.areas:
            if area.area_type == "province" and area.code.casefold() == normalized:
                return True
            if area.area_type == "teryt" and area.code.startswith(province):
                return True
            feature = find_area_geometry(store, area)
            if feature is not None:
                if feature.province_code == province:
                    return True
                if feature.county_code and feature.county_code.startswith(province):
                    return True
        return False
    return True


def _warning_payload_with_geometry(warning: Warning, geometry: dict[str, Any]) -> dict[str, Any]:
    payload = warning.model_dump(mode="json")
    payload["area_codes"] = [area.code for area in warning.areas]
    payload["geometry_status"] = geometry["geometry_status"]
    payload["resolved_areas"] = geometry["resolved_areas"]
    payload["unresolved_areas"] = geometry["unresolved_areas"]
    payload["raw_available"] = True
    return payload


def _areas_to_feature_collection(
    warning: Warning,
    resolved_areas: list[dict[str, Any]],
) -> dict[str, Any]:
    features = [
        {
            "type": "Feature",
            "id": f"{warning.id}:{area['code']}",
            "properties": {
                "warning_id": warning.id,
                "warning_type": warning.warning_type,
                "event": warning.event,
                "level": warning.level,
                "area_type": area["area_type"],
                "code": area["code"],
                "label": area.get("label"),
                "dataset_key": area["dataset_key"],
                "geometry_status": "resolved" if resolved_areas else "missing",
            },
            "geometry": area["geometry"],
        }
        for area in resolved_areas
    ]
    return {"type": "FeatureCollection", "features": features}
