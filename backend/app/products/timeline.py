from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.products import rendering
from app.products.catalog import product_detail
from app.products.classification import classify_product_id


def build_map_timeline(settings: Settings) -> dict[str, Any]:
    layers: list[dict[str, Any]] = []
    for product_id in _timeline_product_ids(settings):
        detail = product_detail(settings, product_id, limit=1, offset=0)
        if detail["frame_count"] <= 0:
            continue
        classification = classify_product_id(product_id)
        first_frame = detail["frames"][0] if detail["frames"] else None
        last_detail = product_detail(
            settings,
            product_id,
            limit=1,
            offset=max(detail["frame_count"] - 1, 0),
        )
        last_frame = last_detail["frames"][0] if last_detail["frames"] else None
        renderable = rendering.renderable_descriptor(settings, product_id)
        layers.append(
            {
                "key": f"product:{product_id}",
                "product_id": product_id,
                "title": detail["description"],
                "kind": "product_frames",
                "category": classification.category,
                "rendering_status": classification.rendering_status,
                "frame_count": detail["frame_count"],
                "missing_frames": detail["missing_frames"],
                "frames_renderable": renderable is not None,
                "renderable": renderable,
                "source_time": detail["retrieved_at"],
                "first_frame_time": first_frame["frame_time"] if first_frame else None,
                "last_frame_time": last_frame["frame_time"] if last_frame else None,
                "stale": detail["stale"],
                "attribution": detail["attribution"],
                "processed_notice": detail["processed_notice"],
                "notes": _layer_notes(classification.rendering_status, renderable),
            }
        )

    return {
        "generated_at": datetime.now(UTC),
        "layers": layers,
        "empty_state": None
        if layers
        else {
            "code": "unsupported_layer",
            "message": "No time-aware product layers are cached yet.",
            "source_keys": ["product"],
        },
    }


def _layer_notes(rendering_status: str, renderable: dict[str, Any] | None) -> list[str]:
    notes = ["Frame timestamps are parsed from public manifest filenames."]
    if renderable is not None:
        notes.append(
            "Frames render server-side as processed IMGW-PIB data "
            "(2 m temperature overlay)."
        )
    elif rendering_status == "download_blocked":
        notes.append(
            "IMGW does not currently serve these files publicly; "
            "frames stay metadata-only."
        )
    else:
        notes.append("Binary product parsing and map rendering are not implemented yet.")
    return notes


def _timeline_product_ids(settings: Settings) -> tuple[str, ...]:
    detail_cache_dir = settings.cache_dir / "product_details"
    if not detail_cache_dir.exists():
        return ()
    product_ids: list[str] = []
    for path in sorted(detail_cache_dir.glob("*.json")):
        product_id = path.stem
        classification = classify_product_id(product_id)
        if classification.availability == "stable_retrievable":
            product_ids.append(product_id)
    return tuple(product_ids)
