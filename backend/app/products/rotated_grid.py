"""Rotated lat/lon grid transforms and resampling for COSMO rendering.

The COSMO grid definition (pole, origin, spacing) is documented by IMGW in
each product's readme.txt; see docs/products/PRODUCT_RESEARCH.md. Formulas
are the standard rotated-pole spherical transforms used by COSMO/CORDEX.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RotatedGridSpec:
    """A regular grid in rotated coordinates.

    ``pole_lat``/``pole_lon`` locate the *north* pole of the rotated system in
    true geographic coordinates. ``first_lat``/``first_lon`` are the rotated
    coordinates of the south-west grid corner.
    """

    pole_lat: float
    pole_lon: float
    first_lat: float
    first_lon: float
    dlat: float
    dlon: float
    ni: int
    nj: int

    @property
    def last_lat(self) -> float:
        return self.first_lat + self.dlat * (self.nj - 1)

    @property
    def last_lon(self) -> float:
        return self.first_lon + self.dlon * (self.ni - 1)


def rotated_to_true(
    rlat: np.ndarray,
    rlon: np.ndarray,
    *,
    pole_lat: float,
    pole_lon: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert rotated coordinates (degrees) to true lat/lon (degrees)."""
    rlat_r = np.radians(np.asarray(rlat, dtype=np.float64))
    rlon_r = np.radians(np.asarray(rlon, dtype=np.float64))
    pole_lat_r = np.radians(pole_lat)

    sin_lat = np.sin(rlat_r) * np.sin(pole_lat_r) + np.cos(rlat_r) * np.cos(rlon_r) * np.cos(
        pole_lat_r
    )
    lat = np.degrees(np.arcsin(np.clip(sin_lat, -1.0, 1.0)))
    lon = pole_lon + np.degrees(
        np.arctan2(
            -np.cos(rlat_r) * np.sin(rlon_r),
            np.cos(pole_lat_r) * np.sin(rlat_r)
            - np.sin(pole_lat_r) * np.cos(rlat_r) * np.cos(rlon_r),
        )
    )
    return lat, _wrap_lon(lon)


def true_to_rotated(
    lat: np.ndarray,
    lon: np.ndarray,
    *,
    pole_lat: float,
    pole_lon: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert true lat/lon (degrees) to rotated coordinates (degrees)."""
    lat_r = np.radians(np.asarray(lat, dtype=np.float64))
    lon_r = np.radians(np.asarray(lon, dtype=np.float64) - pole_lon)
    pole_lat_r = np.radians(pole_lat)

    sin_rlat = np.sin(lat_r) * np.sin(pole_lat_r) + np.cos(lat_r) * np.cos(pole_lat_r) * np.cos(
        lon_r
    )
    rlat = np.degrees(np.arcsin(np.clip(sin_rlat, -1.0, 1.0)))
    rlon = np.degrees(
        np.arctan2(
            -np.cos(lat_r) * np.sin(lon_r),
            np.cos(pole_lat_r) * np.sin(lat_r)
            - np.sin(pole_lat_r) * np.cos(lat_r) * np.cos(lon_r),
        )
    )
    return rlat, _wrap_lon(rlon)


def true_bounds(spec: RotatedGridSpec) -> tuple[float, float, float, float]:
    """Geographic bounding box (west, south, east, north) of the grid edge."""
    edge_rlat: list[np.ndarray] = []
    edge_rlon: list[np.ndarray] = []
    lats = spec.first_lat + spec.dlat * np.arange(spec.nj)
    lons = spec.first_lon + spec.dlon * np.arange(spec.ni)
    edge_rlat.extend((np.full(spec.ni, lats[0]), np.full(spec.ni, lats[-1]), lats, lats))
    edge_rlon.extend((lons, lons, np.full(spec.nj, lons[0]), np.full(spec.nj, lons[-1])))
    lat, lon = rotated_to_true(
        np.concatenate(edge_rlat),
        np.concatenate(edge_rlon),
        pole_lat=spec.pole_lat,
        pole_lon=spec.pole_lon,
    )
    return float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max())


def resample_to_mercator(
    values: np.ndarray,
    spec: RotatedGridSpec,
    *,
    width: int,
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Nearest-neighbour resample onto a Web-Mercator-aligned lat/lon window.

    Returns ``(grid, bounds)`` where ``grid`` has shape (height, width) with
    row 0 at the *northern* edge (image order) and NaN outside the source
    footprint, and ``bounds`` is (west, south, east, north). Rows are spaced
    uniformly in Mercator y so the image can be drawn as a MapLibre image
    source without warping error.
    """
    if values.shape != (spec.nj, spec.ni):
        raise ValueError(
            f"values shape {values.shape} does not match grid {(spec.nj, spec.ni)}."
        )
    west, south, east, north = true_bounds(spec)
    y_north = _mercator_y(north)
    y_south = _mercator_y(south)
    x_span = np.radians(max(east - west, 1e-9))
    height = max(2, round(width * (y_north - y_south) / x_span))

    lon = np.linspace(west, east, width)
    y = np.linspace(y_north, y_south, height)
    lat = _inverse_mercator_y(y)
    lat_grid, lon_grid = np.meshgrid(lat, lon, indexing="ij")

    rlat, rlon = true_to_rotated(
        lat_grid, lon_grid, pole_lat=spec.pole_lat, pole_lon=spec.pole_lon
    )
    i = np.rint((rlon - spec.first_lon) / spec.dlon).astype(np.int64)
    j = np.rint((rlat - spec.first_lat) / spec.dlat).astype(np.int64)
    inside = (i >= 0) & (i < spec.ni) & (j >= 0) & (j < spec.nj)

    grid = np.full(lat_grid.shape, np.nan)
    grid[inside] = values[j[inside], i[inside]]
    return grid, (west, south, east, north)


def _wrap_lon(lon: np.ndarray) -> np.ndarray:
    return (np.asarray(lon) + 180.0) % 360.0 - 180.0


def _mercator_y(lat_deg: float) -> float:
    lat = np.radians(np.clip(lat_deg, -85.05112878, 85.05112878))
    return float(np.log(np.tan(np.pi / 4 + lat / 2)))


def _inverse_mercator_y(y: np.ndarray) -> np.ndarray:
    return np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)
