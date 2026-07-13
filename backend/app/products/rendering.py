"""Rendering pipeline for the first renderable product path (Stage 14).

Scope: 2 m air temperature from the IMGW COSMO ``*_00`` GRIB datasets,
rendered server-side into a Web-Mercator-aligned RGBA PNG that the frontend
draws as a MapLibre image source. Grid parameters were verified against live
GDS sections on 2026-07-05 (docs/products/PRODUCT_RESEARCH.md); a render is
refused — never silently misplaced — when a file stops matching them.
"""

import json
import logging
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from app.core.config import Settings
from app.normalization.models import ATTRIBUTION, PROCESSED_NOTICE
from app.products import grib1
from app.products.png import write_rgba_png
from app.products.rotated_grid import RotatedGridSpec, resample_to_mercator, true_bounds

logger = logging.getLogger(__name__)

class _RenderGate:
    """Bound product rendering and coalesce concurrent requests for one frame."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._active = 0
        self._keys: set[str] = set()

    @contextmanager
    def acquire(self, *, key: str, limit: int):
        with self._condition:
            while key in self._keys or self._active >= limit:
                self._condition.wait()
            self._keys.add(key)
            self._active += 1
        try:
            yield
        finally:
            with self._condition:
                self._keys.remove(key)
                self._active -= 1
                self._condition.notify_all()


# Product files can be ~160 MB. The gate prevents both duplicate upstream
# downloads for a frame and unbounded decode/render memory use.
_RENDER_GATE = _RenderGate()

_LEAD_PATTERN = re.compile(r"_lfff(\d{2})(\d{2})(\d{2})(\d{2})(c?)$")
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9._-]+$")

# Verified against live COSMO_HVD_* GDS sections on 2026-07-05. The product
# readme documents the full model domain; published files carry this cropped
# output grid (0.025 deg ~ 2.8 km, rotated pole shared with the model).
EXPECTED_COSMO_GRID = RotatedGridSpec(
    pole_lat=40.0,
    pole_lon=-170.0,
    first_lat=-2.4,
    first_lon=0.65,
    dlat=0.025,
    dlon=0.025,
    ni=380,
    nj=405,
)


@dataclass(frozen=True)
class VariableSpec:
    key: str
    title: str
    unit: str
    parameter: int
    level_type: int
    level: int
    value_offset: float
    palette: tuple[tuple[float, tuple[int, int, int]], ...]


T2M = VariableSpec(
    key="t2m",
    title="Temperatura powietrza 2 m (COSMO)",
    unit="°C",
    parameter=11,
    level_type=105,
    level=2,
    value_offset=-273.15,
    palette=(
        (-30.0, (60, 0, 120)),
        (-20.0, (40, 60, 180)),
        (-10.0, (60, 130, 220)),
        (0.0, (160, 220, 240)),
        (10.0, (110, 190, 90)),
        (20.0, (250, 220, 80)),
        (30.0, (245, 130, 40)),
        (40.0, (200, 20, 30)),
    ),
)

VARIABLES: dict[str, VariableSpec] = {T2M.key: T2M}

_RENDERABLE_PRODUCT_PATTERN = re.compile(r"^COSMO_HVD_(00|06|12|18)_00$")


class RenderError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class RenderResult:
    png_path: Path
    metadata: dict[str, Any]
    from_cache: bool


def product_is_renderable(product_id: str) -> bool:
    return _RENDERABLE_PRODUCT_PATTERN.match(product_id) is not None


def renderable_variables(product_id: str) -> list[VariableSpec]:
    if not product_is_renderable(product_id):
        return []
    return list(VARIABLES.values())


def parse_lead_hours(filename: str) -> float | None:
    """Forecast lead in hours from a COSMO ``lfffDDHHMMSS`` suffix.

    Returns None for non-forecast files, including the per-run constant-field
    file (``...c``), which must never be treated as a forecast frame.
    """
    match = _LEAD_PATTERN.search(filename)
    if match is None or match.group(5) == "c":
        return None
    days, hours, minutes, seconds = (int(part) for part in match.groups()[:4])
    return days * 24 + hours + minutes / 60 + seconds / 3600


def is_constant_file(filename: str) -> bool:
    match = _LEAD_PATTERN.search(filename)
    return match is not None and match.group(5) == "c"


def frame_render_state(settings: Settings, product_id: str, filename: str) -> dict[str, Any]:
    """Renderability of one frame, with an explicit reason when negative."""
    if not product_is_renderable(product_id):
        return {"renderable": False, "reason": "product_not_renderable"}
    if is_constant_file(filename):
        return {"renderable": False, "reason": "constant_field_file"}
    lead = parse_lead_hours(filename)
    if lead is None:
        return {"renderable": False, "reason": "not_a_forecast_frame"}
    if lead > settings.product_render_max_lead_hours:
        return {"renderable": False, "reason": "lead_beyond_render_window"}
    if lead % settings.product_render_lead_step_hours != 0:
        return {"renderable": False, "reason": "lead_not_on_render_step"}
    return {"renderable": True, "reason": None}


def render_bounds() -> tuple[float, float, float, float]:
    return true_bounds(EXPECTED_COSMO_GRID)


def image_coordinates() -> list[list[float]]:
    """MapLibre image-source corners: TL, TR, BR, BL as [lon, lat]."""
    west, south, east, north = render_bounds()
    return [[west, north], [east, north], [east, south], [west, south]]


def renderable_descriptor(settings: Settings, product_id: str) -> dict[str, Any] | None:
    """Map-layer descriptor for a renderable product, or None.

    Only returned when frames can actually be rendered; metadata-only
    products must never receive one.
    """
    variables = renderable_variables(product_id)
    if not variables:
        return None
    west, south, east, north = render_bounds()
    return {
        "variables": [
            {
                "key": variable.key,
                "title": variable.title,
                "unit": variable.unit,
                "legend": palette_legend(variable),
            }
            for variable in variables
        ],
        "default_variable": variables[0].key,
        "bounds": [west, south, east, north],
        "image_coordinates": image_coordinates(),
        "render_url_template": (
            f"/api/v1/products/{product_id}/render/{{file}}?variable={{variable}}"
        ),
        "max_lead_hours": settings.product_render_max_lead_hours,
        "lead_step_hours": settings.product_render_lead_step_hours,
        "grid_note": (
            "COSMO rotated lat/lon 0.025 deg grid reprojected to Web Mercator; "
            "grid verified against live GDS sections on 2026-07-05."
        ),
        "attribution": ATTRIBUTION,
        "processed_notice": PROCESSED_NOTICE,
    }


def render_cache_path(
    settings: Settings, product_id: str, filename: str, variable: str
) -> Path:
    return (
        _renders_dir(settings, product_id) / f"{_safe(filename)}.{_safe(variable)}.png"
    )


def read_render_metadata(png_path: Path) -> dict[str, Any] | None:
    sidecar = png_path.with_suffix(".json")
    if not sidecar.exists():
        return None
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def render_frame(
    settings: Settings,
    *,
    product_id: str,
    filename: str,
    url: str,
    variable_key: str,
) -> RenderResult:
    variable = VARIABLES.get(variable_key)
    if variable is None or not product_is_renderable(product_id):
        raise RenderError(
            "not_renderable",
            f"Product {product_id} has no renderable variable {variable_key}.",
            status_code=404,
        )
    state = frame_render_state(settings, product_id, filename)
    if not state["renderable"]:
        raise RenderError(
            "frame_not_renderable",
            f"Frame {filename} is not renderable: {state['reason']}.",
            status_code=404,
        )

    png_path = render_cache_path(settings, product_id, filename, variable.key)
    metadata = read_render_metadata(png_path)
    if png_path.exists() and metadata is not None:
        return RenderResult(png_path=png_path, metadata=metadata, from_cache=True)

    render_key = f"{product_id}:{filename}:{variable.key}"
    with _RENDER_GATE.acquire(
        key=render_key,
        limit=settings.product_render_max_concurrent,
    ):
        metadata = read_render_metadata(png_path)
        if png_path.exists() and metadata is not None:
            return RenderResult(png_path=png_path, metadata=metadata, from_cache=True)
        return _render_uncached(
            settings,
            product_id=product_id,
            filename=filename,
            url=url,
            variable=variable,
            png_path=png_path,
        )


def _render_uncached(
    settings: Settings,
    *,
    product_id: str,
    filename: str,
    url: str,
    variable: VariableSpec,
    png_path: Path,
) -> RenderResult:
    data, retrieved_at = _read_or_fetch_binary(
        settings, product_id=product_id, filename=filename, url=url
    )
    record = grib1.find_record(
        data,
        parameter=variable.parameter,
        level_type=variable.level_type,
        level=variable.level,
    )
    if record is None:
        raise RenderError(
            "variable_missing",
            f"GRIB file {filename} has no record for {variable.key}.",
        )
    spec = _grid_spec_from_record(record)
    _verify_grid(spec)

    try:
        values = record.values() + variable.value_offset
    except grib1.Grib1Error as exc:
        raise RenderError("decode_failed", str(exc)) from exc

    grid, bounds = resample_to_mercator(
        values, spec, width=settings.product_render_width
    )
    pixels = _apply_palette(grid, variable.palette)
    frame_time = record.valid_time.isoformat() if record.valid_time else None
    run_time = record.reference_time.isoformat()
    rendered_at = datetime.now(UTC).isoformat()
    png_bytes = write_rgba_png(
        pixels,
        texts={
            "Attribution": ATTRIBUTION,
            "ProcessedNotice": PROCESSED_NOTICE,
            "Variable": f"{variable.title} [{variable.unit}]",
            "FrameTime": frame_time or "",
            "RunTime": run_time,
            "RetrievedAt": retrieved_at,
            "RenderedAt": rendered_at,
        },
    )
    metadata = {
        "product_id": product_id,
        "file": filename,
        "variable": variable.key,
        "variable_title": variable.title,
        "unit": variable.unit,
        "frame_time": frame_time,
        "run_time": run_time,
        "retrieved_at": retrieved_at,
        "rendered_at": rendered_at,
        "bounds": list(bounds),
        "width": pixels.shape[1],
        "height": pixels.shape[0],
        "value_min": _finite_or_none(np.nanmin(grid)),
        "value_max": _finite_or_none(np.nanmax(grid)),
        "attribution": ATTRIBUTION,
        "processed_notice": PROCESSED_NOTICE,
    }
    png_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.write_bytes(png_bytes)
    png_path.with_suffix(".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _enforce_render_retention(settings, product_id)
    logger.info(
        "Rendered product frame product_id=%s file=%s variable=%s bounds=%s",
        product_id,
        filename,
        variable.key,
        bounds,
    )
    return RenderResult(png_path=png_path, metadata=metadata, from_cache=False)


def _read_or_fetch_binary(
    settings: Settings, *, product_id: str, filename: str, url: str
) -> tuple[bytes, str]:
    binary_path = _binaries_dir(settings, product_id) / _safe(filename)
    meta_path = binary_path.with_name(binary_path.name + ".meta.json")
    if binary_path.exists():
        retrieved_at = None
        try:
            retrieved_at = json.loads(meta_path.read_text(encoding="utf-8"))["retrieved_at"]
        except (OSError, ValueError, KeyError):
            pass
        if retrieved_at is None:
            retrieved_at = datetime.fromtimestamp(
                binary_path.stat().st_mtime, tz=UTC
            ).isoformat()
        return binary_path.read_bytes(), retrieved_at

    data, retrieved_at = _download_binary(settings, url=url, filename=filename)
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_bytes(data)
    meta_path.write_text(
        json.dumps({"retrieved_at": retrieved_at, "url": url, "bytes": len(data)}),
        encoding="utf-8",
    )
    _enforce_binary_retention(settings, product_id)
    return data, retrieved_at


def _download_binary(settings: Settings, *, url: str, filename: str) -> tuple[bytes, str]:
    max_bytes = settings.product_file_max_mb * 1024 * 1024
    retrieved_at = datetime.now(UTC).isoformat()
    try:
        with httpx.Client(
            timeout=settings.product_download_timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "MeteoLens/0.1 (+https://github.com/Adiker/MeteoLens)"},
        ) as client:
            with client.stream("GET", url) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    # IMGW answers 307 -> HTML datastore page when a product
                    # path is not publicly downloadable (e.g. radar composites).
                    raise RenderError(
                        "download_blocked",
                        f"IMGW redirected the file download for {filename}; "
                        "the product path is not publicly downloadable.",
                    )
                if response.status_code != 200:
                    raise RenderError(
                        "download_failed",
                        f"IMGW returned HTTP {response.status_code} for {filename}.",
                    )
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise RenderError(
                            "file_too_large",
                            f"{filename} exceeds the configured "
                            f"{settings.product_file_max_mb} MB download limit.",
                        )
                    chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise RenderError("download_failed", f"Download of {filename} failed: {exc}") from exc

    data = b"".join(chunks)
    if not data.startswith(grib1.GRIB_MAGIC):
        # Missing files come back as HTTP 200 HTML pages, so the magic check
        # is the reliable missing-frame signal.
        raise RenderError(
            "frame_missing",
            f"IMGW did not return a GRIB file for {filename}; "
            "the frame is missing at the source.",
            status_code=404,
        )
    return data, retrieved_at


def _grid_spec_from_record(record: grib1.Grib1Record) -> RotatedGridSpec:
    grid = record.grid
    if grid is None or not grid.rotated:
        raise RenderError(
            "grid_mismatch", "GRIB record does not use the expected rotated grid."
        )
    if grid.south_pole_lat is None or grid.south_pole_lon is None:
        raise RenderError("grid_mismatch", "GRIB rotated grid is missing pole metadata.")
    first_lat = min(grid.lat1, grid.lat2)
    first_lon = min(grid.lon1, grid.lon2)
    dlat = grid.dj or (abs(grid.lat2 - grid.lat1) / max(grid.nj - 1, 1))
    dlon = grid.di or (abs(grid.lon2 - grid.lon1) / max(grid.ni - 1, 1))
    return RotatedGridSpec(
        pole_lat=-grid.south_pole_lat,
        pole_lon=_wrap_degrees(grid.south_pole_lon + 180.0),
        first_lat=first_lat,
        first_lon=first_lon,
        dlat=dlat,
        dlon=dlon,
        ni=grid.ni,
        nj=grid.nj,
    )


def _verify_grid(spec: RotatedGridSpec) -> None:
    expected = EXPECTED_COSMO_GRID
    mismatches: list[str] = []
    if spec.ni != expected.ni or spec.nj != expected.nj:
        mismatches.append(f"size {spec.ni}x{spec.nj} != {expected.ni}x{expected.nj}")
    for name, actual, wanted, tolerance in (
        ("pole_lat", spec.pole_lat, expected.pole_lat, 0.01),
        ("pole_lon", spec.pole_lon, expected.pole_lon, 0.01),
        ("first_lat", spec.first_lat, expected.first_lat, 0.05),
        ("first_lon", spec.first_lon, expected.first_lon, 0.05),
        ("dlat", spec.dlat, expected.dlat, 0.001),
        ("dlon", spec.dlon, expected.dlon, 0.001),
    ):
        if abs(actual - wanted) > tolerance:
            mismatches.append(f"{name} {actual} != {wanted}")
    if mismatches:
        raise RenderError(
            "grid_mismatch",
            "GRIB grid no longer matches the reviewed COSMO grid ("
            + "; ".join(mismatches)
            + "). Refusing to render at a wrong map position; re-verify the "
            "grid and update EXPECTED_COSMO_GRID.",
        )


def _apply_palette(
    grid: np.ndarray,
    palette: tuple[tuple[float, tuple[int, int, int]], ...],
) -> np.ndarray:
    stops = np.array([value for value, _ in palette])
    channels = np.array([color for _, color in palette], dtype=np.float64)
    valid = np.isfinite(grid)
    flat = np.where(valid, grid, stops[0])
    pixels = np.zeros((*grid.shape, 4), dtype=np.uint8)
    for channel in range(3):
        pixels[..., channel] = np.interp(
            flat, stops, channels[:, channel]
        ).round().astype(np.uint8)
    pixels[..., 3] = np.where(valid, 190, 0).astype(np.uint8)
    return pixels


def palette_legend(variable: VariableSpec) -> list[dict[str, Any]]:
    return [
        {"value": value, "color": f"#{r:02x}{g:02x}{b:02x}"}
        for value, (r, g, b) in variable.palette
    ]


def _enforce_binary_retention(settings: Settings, product_id: str) -> None:
    _evict_files(
        _binaries_dir(settings, product_id),
        max_files=settings.product_binary_max_files,
        max_age_hours=settings.product_file_retention_hours,
        group_suffixes=(".meta.json",),
    )


def _enforce_render_retention(settings: Settings, product_id: str) -> None:
    _evict_files(
        _renders_dir(settings, product_id),
        max_files=settings.product_max_cached_files,
        max_age_hours=settings.product_file_retention_hours,
        group_suffixes=(".json",),
        primary_suffix=".png",
    )


def _evict_files(
    directory: Path,
    *,
    max_files: int,
    max_age_hours: int,
    group_suffixes: tuple[str, ...],
    primary_suffix: str | None = None,
) -> None:
    """Delete oldest-first beyond ``max_files`` and anything older than
    ``max_age_hours``. Sidecar files listed in ``group_suffixes`` are removed
    together with their primary file."""
    if not directory.exists():
        return
    now = datetime.now(UTC).timestamp()
    primaries = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and not any(path.name.endswith(suffix) for suffix in group_suffixes)
        and (primary_suffix is None or path.name.endswith(primary_suffix))
    ]
    primaries.sort(key=lambda path: path.stat().st_mtime)

    def _remove(path: Path) -> None:
        path.unlink(missing_ok=True)
        for suffix in group_suffixes:
            if primary_suffix is not None and path.name.endswith(primary_suffix):
                sidecar = path.with_name(path.name[: -len(primary_suffix)] + suffix)
            else:
                sidecar = path.with_name(path.name + suffix)
            sidecar.unlink(missing_ok=True)

    overflow = len(primaries) - max_files
    for path in primaries[: max(overflow, 0)]:
        _remove(path)
        logger.info("Evicted cached product file (count limit): %s", path)
    for path in primaries[max(overflow, 0) :]:
        if now - path.stat().st_mtime > max_age_hours * 3600:
            _remove(path)
            logger.info("Evicted cached product file (age limit): %s", path)


def _binaries_dir(settings: Settings, product_id: str) -> Path:
    return settings.cache_dir.parent / "products" / "binaries" / _safe(product_id)


def _renders_dir(settings: Settings, product_id: str) -> Path:
    return settings.cache_dir.parent / "products" / "renders" / _safe(product_id)


def _safe(component: str) -> str:
    cleaned = component.replace("/", "_")
    if not _SAFE_COMPONENT.match(cleaned):
        raise RenderError(
            "invalid_name", f"Unsafe file or product name: {component!r}", status_code=422
        )
    return cleaned


def _wrap_degrees(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def _finite_or_none(value: float) -> float | None:
    return round(float(value), 2) if np.isfinite(value) else None
