"""Scheduled refresh of product detail manifests (Stage 14).

Only the frame-list manifests are refreshed here; binary downloads happen
lazily in the render pipeline (optionally prefetched for the newest frames).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import Settings
from app.core.logging import log_source_fetch
from app.products import rendering
from app.products.detail_cache import ProductDetailCache
from app.products.frames import build_frame_records

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProductDetailRefreshResult:
    product_id: str
    status: str
    file_count: int = 0
    skipped: bool = False
    error: str | None = None
    prefetched: list[str] = field(default_factory=list)


async def refresh_product_details(
    settings: Settings,
    *,
    force: bool = False,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[ProductDetailRefreshResult]:
    """Refresh detail manifests for the configured product IDs, oldest TTL wins.

    Runs sequentially on purpose: parallel manifest fetches (and especially
    parallel binary prefetches) would multiply load on IMGW.
    """
    cache = ProductDetailCache(settings.cache_dir)
    results: list[ProductDetailRefreshResult] = []
    async with httpx.AsyncClient(
        timeout=settings.imgw_timeout_seconds,
        headers={
            "Accept": "application/json",
            "User-Agent": "MeteoLens/0.1 (+https://github.com/Adiker/MeteoLens)",
        },
        transport=transport,
    ) as client:
        for product_id in settings.product_refresh_id_list:
            results.append(
                await _refresh_one(settings, cache, client, product_id, force=force)
            )
    _enforce_manifest_limit(settings, cache)
    return results


async def _refresh_one(
    settings: Settings,
    cache: ProductDetailCache,
    client: httpx.AsyncClient,
    product_id: str,
    *,
    force: bool,
) -> ProductDetailRefreshResult:
    cached = cache.read(product_id)
    if cached is not None and not force and cached.error is None:
        age = (datetime.now(UTC) - cached.retrieved_at).total_seconds()
        if age <= settings.product_detail_cache_seconds:
            return ProductDetailRefreshResult(
                product_id=product_id,
                status="fresh",
                file_count=len(cached.files),
                skipped=True,
            )

    base_url = str(settings.imgw_base_url).rstrip("/")
    url = f"{base_url}/api/data/product/id/{product_id}"
    retrieved_at = datetime.now(UTC)
    try:
        response = await client.get(url)
        response.raise_for_status()
        files = _parse_detail_payload(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        error = str(exc)
        cache.write_error(product_id=product_id, url=url, error=error)
        log_source_fetch(
            source_key=f"product_detail:{product_id}",
            url=url,
            status="error",
            retrieved_at=retrieved_at.isoformat(),
            error=error,
        )
        return ProductDetailRefreshResult(product_id=product_id, status="error", error=error)

    cache.write_success(
        product_id=product_id,
        url=url,
        retrieved_at=retrieved_at,
        files=files,
    )
    log_source_fetch(
        source_key=f"product_detail:{product_id}",
        url=url,
        status="success",
        retrieved_at=retrieved_at.isoformat(),
        record_count=len(files),
    )
    prefetched = await _prefetch_renders(settings, product_id, files)
    return ProductDetailRefreshResult(
        product_id=product_id,
        status="success",
        file_count=len(files),
        prefetched=prefetched,
    )


def _parse_detail_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if payload.get("status") is False:
            raise ValueError(str(payload.get("message") or "Product could not be found"))
        payload = payload.get("files", [])
    if not isinstance(payload, list):
        raise ValueError("Unexpected product detail payload shape.")
    return [row for row in payload if isinstance(row, dict)]


async def _prefetch_renders(
    settings: Settings,
    product_id: str,
    files: list[dict[str, Any]],
) -> list[str]:
    """Optionally pre-render the newest renderable frames after a refresh."""
    limit = settings.product_render_prefetch_frames
    if limit <= 0 or not rendering.product_is_renderable(product_id):
        return []
    frames = build_frame_records(product_id, files)
    candidates = [
        frame
        for frame in frames
        if frame["url"]
        and rendering.frame_render_state(settings, product_id, frame["file"])["renderable"]
    ]
    candidates.sort(key=lambda frame: frame["frame_time"] or "", reverse=True)
    prefetched: list[str] = []
    for frame in candidates[:limit]:
        for variable in rendering.renderable_variables(product_id):
            try:
                await asyncio.to_thread(
                    rendering.render_frame,
                    settings,
                    product_id=product_id,
                    filename=frame["file"],
                    url=frame["url"],
                    variable_key=variable.key,
                )
                prefetched.append(frame["file"])
            except rendering.RenderError as exc:
                logger.warning(
                    "Prefetch render failed product_id=%s file=%s: %s",
                    product_id,
                    frame["file"],
                    exc,
                )
    return prefetched


def _enforce_manifest_limit(settings: Settings, cache: ProductDetailCache) -> None:
    manifests = [path for path in cache.cache_dir.glob("*.json") if path.is_file()]
    overflow = len(manifests) - settings.product_max_detail_manifests
    if overflow <= 0:
        return
    manifests.sort(key=lambda path: path.stat().st_mtime)
    for path in manifests[:overflow]:
        path.unlink(missing_ok=True)
        logger.info("Evicted product detail manifest (count limit): %s", path)
