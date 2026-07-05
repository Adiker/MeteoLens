import asyncio
from datetime import UTC, datetime, timedelta

import httpx

from app.core.config import Settings
from app.products.detail_cache import ProductDetailCache
from app.products.refresh import refresh_product_details


def _settings(tmp_path, **overrides) -> Settings:
    return Settings(
        cache_dir=tmp_path / "cache",
        geometry_dir=tmp_path / "geometry",
        imgw_base_url="https://danepubliczne.imgw.pl",
        **overrides,
    )


def _run(coro):
    return asyncio.run(coro)


def _detail_handler(calls: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        product_id = str(request.url).rsplit("/", 1)[-1]
        if product_id == "COSMO_HVD_00_00":
            return httpx.Response(
                200,
                json=[
                    {"file": "202607040000_202607040000_lfff00000000", "url": "https://x/1"},
                    {"file": "readme.txt", "url": "https://x/readme"},
                ],
            )
        if product_id == "MISSING_PRODUCT":
            return httpx.Response(
                200, json={"status": False, "message": "Product could not be found"}
            )
        return httpx.Response(500)

    return handler


def test_refresh_writes_detail_manifest(tmp_path) -> None:
    settings = _settings(tmp_path, product_refresh_ids="COSMO_HVD_00_00")
    calls: list[str] = []
    results = _run(
        refresh_product_details(
            settings, transport=httpx.MockTransport(_detail_handler(calls))
        )
    )
    assert [result.status for result in results] == ["success"]
    assert results[0].file_count == 2
    cached = ProductDetailCache(settings.cache_dir).read("COSMO_HVD_00_00")
    assert cached is not None
    assert cached.error is None
    assert len(cached.files) == 2
    assert calls and calls[0].endswith("/api/data/product/id/COSMO_HVD_00_00")


def test_refresh_skips_fresh_manifest_within_ttl(tmp_path) -> None:
    settings = _settings(tmp_path, product_refresh_ids="COSMO_HVD_00_00")
    cache = ProductDetailCache(settings.cache_dir)
    cache.write_success(
        product_id="COSMO_HVD_00_00",
        url="https://danepubliczne.imgw.pl/api/data/product/id/COSMO_HVD_00_00",
        retrieved_at=datetime.now(UTC),
        files=[{"file": "a", "url": "https://x/a"}],
    )
    calls: list[str] = []
    results = _run(
        refresh_product_details(
            settings, transport=httpx.MockTransport(_detail_handler(calls))
        )
    )
    assert results[0].status == "fresh"
    assert results[0].skipped is True
    assert calls == []


def test_refresh_refetches_stale_manifest(tmp_path) -> None:
    settings = _settings(tmp_path, product_refresh_ids="COSMO_HVD_00_00")
    cache = ProductDetailCache(settings.cache_dir)
    cache.write_success(
        product_id="COSMO_HVD_00_00",
        url="https://danepubliczne.imgw.pl/api/data/product/id/COSMO_HVD_00_00",
        retrieved_at=datetime.now(UTC)
        - timedelta(seconds=settings.product_detail_cache_seconds + 60),
        files=[],
    )
    calls: list[str] = []
    results = _run(
        refresh_product_details(
            settings, transport=httpx.MockTransport(_detail_handler(calls))
        )
    )
    assert results[0].status == "success"
    assert len(calls) == 1


def test_refresh_missing_product_records_error_entry(tmp_path) -> None:
    settings = _settings(tmp_path, product_refresh_ids="MISSING_PRODUCT")
    calls: list[str] = []
    results = _run(
        refresh_product_details(
            settings, transport=httpx.MockTransport(_detail_handler(calls))
        )
    )
    assert results[0].status == "error"
    assert "Product could not be found" in (results[0].error or "")
    cached = ProductDetailCache(settings.cache_dir).read("MISSING_PRODUCT")
    assert cached is not None
    assert cached.error is not None
    assert cached.files == []


def test_refresh_http_error_records_error_entry(tmp_path) -> None:
    settings = _settings(tmp_path, product_refresh_ids="BROKEN_PRODUCT")
    results = _run(
        refresh_product_details(settings, transport=httpx.MockTransport(_detail_handler([])))
    )
    assert results[0].status == "error"
    cached = ProductDetailCache(settings.cache_dir).read("BROKEN_PRODUCT")
    assert cached is not None
    assert cached.error is not None


def test_manifest_count_limit_evicts_oldest(tmp_path) -> None:
    settings = _settings(
        tmp_path,
        product_refresh_ids="COSMO_HVD_00_00",
        product_max_detail_manifests=2,
    )
    cache = ProductDetailCache(settings.cache_dir)
    old = datetime.now(UTC) - timedelta(hours=5)
    for index, product_id in enumerate(["OLD_A", "OLD_B"]):
        cache.write_success(
            product_id=product_id,
            url=f"https://x/{product_id}",
            retrieved_at=old,
            files=[],
        )
        path = cache.cache_dir / f"{product_id}.json"
        stamp = (old + timedelta(minutes=index)).timestamp()
        import os

        os.utime(path, (stamp, stamp))

    _run(
        refresh_product_details(
            settings, transport=httpx.MockTransport(_detail_handler([]))
        )
    )

    remaining = sorted(path.stem for path in cache.cache_dir.glob("*.json"))
    assert "COSMO_HVD_00_00" in remaining
    assert len(remaining) == 2
    assert "OLD_A" not in remaining
