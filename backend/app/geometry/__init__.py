"""Reviewed geometry dataset loading and spatial helpers."""

from app.geometry.loader import GeometryStore, get_geometry_store, reset_geometry_store
from app.geometry.spatial import (
    point_in_geometry,
    resolve_warning_geometries,
    warnings_matching_point,
)

__all__ = [
    "GeometryStore",
    "get_geometry_store",
    "point_in_geometry",
    "reset_geometry_store",
    "resolve_warning_geometries",
    "warnings_matching_point",
]
