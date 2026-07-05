from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.imgw.cache import SourceCache
from app.normalization.models import ATTRIBUTION, PROCESSED_NOTICE, ProductManifest, SourceMetadata
from app.products import rendering
from app.products.classification import RESEARCH_DATE, classify_product_id
from app.products.detail_cache import ProductDetailCache
from app.products.frames import build_frame_records


def list_products(settings: Settings) -> dict[str, Any]:
    cache = SourceCache(settings.cache_dir)
    cached = cache.read("product")
    retrieved_at = cached.retrieved_at if cached else None
    manifests = _manifest_records(cached)
    products: list[dict[str, Any]] = []
    for manifest in manifests:
        classification = classify_product_id(manifest.source_id)
        products.append(
            {
                "id": manifest.source_id,
                "description": manifest.description,
                "manifest_url": manifest.url,
                "category": classification.category,
                "availability": classification.availability,
                "rendering_status": classification.rendering_status,
                "high_value": classification.high_value,
                "format_notes": classification.format_notes,
                "research_date": RESEARCH_DATE,
                "notes": classification.notes,
                "missing_fields": manifest.missing_fields,
                "source": manifest.source.model_dump(mode="json"),
            }
        )
    return {
        "generated_at": datetime.now(UTC),
        "retrieved_at": retrieved_at,
        "research_date": RESEARCH_DATE,
        "attribution": ATTRIBUTION,
        "processed_notice": PROCESSED_NOTICE,
        "products": products,
        "empty_state": None
        if products
        else {
            "code": "cache_empty",
            "message": "Product manifest cache is empty.",
            "source_keys": ["product"],
        },
    }


def product_detail(
    settings: Settings,
    product_id: str,
    *,
    limit: int = 120,
    offset: int = 0,
) -> dict[str, Any]:
    classification = classify_product_id(product_id)
    manifest = _manifest_by_id(settings, product_id)
    detail_cache = ProductDetailCache(settings.cache_dir)
    cached_detail = detail_cache.read(product_id)
    source = manifest.source if manifest else _fallback_source(settings, product_id)
    renderable = rendering.renderable_descriptor(settings, product_id)
    if cached_detail is None:
        return {
            "renderable": renderable,
            "generated_at": datetime.now(UTC),
            "product_id": product_id,
            "description": manifest.description if manifest else product_id,
            "category": classification.category,
            "availability": classification.availability,
            "rendering_status": classification.rendering_status,
            "format_notes": classification.format_notes,
            "research_date": RESEARCH_DATE,
            "source": source.model_dump(mode="json"),
            "retrieved_at": None,
            "frames": [],
            "frame_count": 0,
            "limit": limit,
            "offset": offset,
            "missing_frames": 0,
            "stale": False,
            "attribution": ATTRIBUTION,
            "processed_notice": PROCESSED_NOTICE,
            "empty_state": {
                "code": "product_unavailable"
                if classification.availability == "listed_missing"
                else "cache_empty",
                "message": "Product frame manifest is not cached yet.",
                "source_keys": ["product"],
            },
        }

    all_frames = build_frame_records(product_id, cached_detail.files)
    page = all_frames[offset : offset + limit]
    if renderable is not None:
        for frame in page:
            _annotate_render_state(settings, product_id, frame, renderable)
    missing_frames = sum(1 for frame in all_frames if frame["missing"])
    stale = _is_stale(cached_detail.retrieved_at, settings.product_detail_cache_seconds)
    return {
        "renderable": renderable,
        "generated_at": datetime.now(UTC),
        "product_id": product_id,
        "description": manifest.description if manifest else product_id,
        "category": classification.category,
        "availability": classification.availability,
        "rendering_status": classification.rendering_status,
        "format_notes": classification.format_notes,
        "research_date": RESEARCH_DATE,
        "source": _detail_source(cached_detail).model_dump(mode="json"),
        "retrieved_at": cached_detail.retrieved_at,
        "frames": page,
        "frame_count": len(all_frames),
        "limit": limit,
        "offset": offset,
        "missing_frames": missing_frames,
        "stale": stale,
        "attribution": ATTRIBUTION,
        "processed_notice": PROCESSED_NOTICE,
        "empty_state": None
        if page
        else {
            "code": "frame_missing",
            "message": "No frames matched the requested window.",
            "source_keys": ["product"],
        },
        "error": cached_detail.error,
    }


def _annotate_render_state(
    settings: Settings,
    product_id: str,
    frame: dict[str, Any],
    renderable: dict[str, Any],
) -> None:
    state = rendering.frame_render_state(settings, product_id, frame["file"])
    frame["renderable"] = state["renderable"]
    frame["renderable_reason"] = state["reason"]
    if not state["renderable"]:
        return
    variable = renderable["default_variable"]
    frame["render_url"] = (
        f"/api/v1/products/{product_id}/render/{frame['file']}?variable={variable}"
    )
    frame["render_ready"] = rendering.render_cache_path(
        settings, product_id, frame["file"], variable
    ).exists()


def _detail_source(cached_detail) -> SourceMetadata:
    return SourceMetadata(
        source_key="product",
        url=cached_detail.url,
        retrieved_at=cached_detail.retrieved_at,
    )


def _manifest_records(cached) -> list[ProductManifest]:
    if cached is None or cached.error or not cached.normalized_payload:
        return []
    records: list[ProductManifest] = []
    for row in cached.normalized_payload:
        records.append(ProductManifest.model_validate(row))
    return records


def _manifest_by_id(settings: Settings, product_id: str) -> ProductManifest | None:
    for manifest in _manifest_records(SourceCache(settings.cache_dir).read("product")):
        if manifest.source_id == product_id:
            return manifest
    return None


def _fallback_source(settings: Settings, product_id: str) -> SourceMetadata:
    base_url = str(settings.imgw_base_url).rstrip("/")
    return SourceMetadata(
        source_key="product",
        url=f"{base_url}/api/data/product/id/{product_id}",
        retrieved_at=datetime.now(UTC),
    )


def _is_stale(retrieved_at: datetime, ttl_seconds: int) -> bool:
    age = (datetime.now(UTC) - retrieved_at).total_seconds()
    return age > ttl_seconds
