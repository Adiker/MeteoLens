from datetime import UTC, datetime
from typing import Any, Literal

from app.products.classification import ProductCategory, classify_product_id

FrameKind = Literal["forecast_lead", "observation", "preview", "metadata"]


def parse_frame_time(filename: str, *, category: ProductCategory) -> datetime | None:
    lowered = filename.lower()
    if lowered in {"readme.txt", "readme"}:
        return None

    if category == "grib_model":
        parts = filename.split("_")
        if len(parts) >= 2 and len(parts[1]) == 12 and parts[1].isdigit():
            return _parse_yyyymmddhhmm(parts[1])
        return None

    stem = filename.split(".", 1)[0]
    if len(stem) >= 14 and stem[:14].isdigit():
        return _parse_yyyymmddhhmmss(stem[:14])

    return None


def frame_kind(filename: str, *, category: ProductCategory) -> FrameKind:
    lowered = filename.lower()
    if lowered.endswith(".png"):
        return "preview"
    if lowered.endswith(".txt"):
        return "metadata"
    if category == "grib_model":
        return "forecast_lead"
    return "observation"


def build_frame_records(
    product_id: str,
    files: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    classification = classify_product_id(product_id)
    frames: list[dict[str, Any]] = []
    for index, row in enumerate(files):
        if not isinstance(row, dict):
            continue
        filename = str(row.get("file") or "")
        if not filename:
            continue
        frame_time = parse_frame_time(filename, category=classification.category)
        kind = frame_kind(filename, category=classification.category)
        frames.append(
            {
                "index": index,
                "file": filename,
                "url": str(row.get("url") or ""),
                "frame_time": frame_time.isoformat() if frame_time else None,
                "frame_kind": kind,
                "rendering_status": classification.rendering_status,
                "missing": frame_time is None and kind != "metadata",
            }
        )
    return frames


def _parse_yyyymmddhhmm(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%d%H%M").replace(tzinfo=UTC)


def _parse_yyyymmddhhmmss(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
