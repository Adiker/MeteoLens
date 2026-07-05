import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

import app.api.v1 as v1
from app.core.config import Settings
from app.imgw.cache import SourceCache
from app.imgw.parsers import parse_source
from app.main import app
from app.normalization.models import SourceMetadata
from app.products.detail_cache import ProductDetailCache
from tests.grib_fixtures import encode_grib1_message
from tests.test_parsers import load_fixture


def _settings(tmp_path) -> Settings:
    return Settings(
        cache_dir=tmp_path,
        geometry_dir=tmp_path / "geometry",
        imgw_base_url="https://danepubliczne.imgw.pl",
    )


def _source_metadata(source_key: str) -> SourceMetadata:
    return SourceMetadata(
        source_key=source_key,
        url=f"https://danepubliczne.imgw.pl/api/data/{source_key}",
        retrieved_at=datetime(2026, 6, 30, 7, 30, tzinfo=UTC),
    )


def _write_cached_source(cache: SourceCache, source_key: str) -> None:
    metadata = _source_metadata(source_key)
    parse_result = parse_source(source_key, load_fixture(source_key), metadata)
    cache.write_success(
        source_key=source_key,
        url=metadata.url,
        retrieved_at=metadata.retrieved_at,
        raw_payload=load_fixture(source_key),
        normalized_payload=[record.model_dump(mode="json") for record in parse_result.records],
        parser_warnings=parse_result.warnings,
    )


def _seed_product_detail(tmp_path, product_id: str) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "product_detail" / f"{product_id}.json"
    files = json.loads(fixture_path.read_text(encoding="utf-8"))
    ProductDetailCache(tmp_path).write_success(
        product_id=product_id,
        url=f"https://danepubliczne.imgw.pl/api/data/product/id/{product_id}",
        retrieved_at=datetime(2026, 6, 30, 8, 0, tzinfo=UTC),
        files=files,
    )


@pytest.fixture
def seeded_products(tmp_path, monkeypatch):
    _write_cached_source(SourceCache(tmp_path), "product")
    _seed_product_detail(tmp_path, "COMPO_SRI.comp.sri")
    _seed_product_detail(tmp_path, "COSMO_HVD_00_00")
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    return tmp_path


def test_products_endpoint_classifies_manifest_entries(seeded_products) -> None:
    response = TestClient(app).get("/api/v1/products")
    assert response.status_code == 200
    payload = response.json()
    assert payload["research_date"] == "2026-07-05"
    assert len(payload["products"]) == 2
    by_id = {item["id"]: item for item in payload["products"]}
    assert by_id["COSMO_HVD_00_00"]["availability"] == "stable_retrievable"
    assert by_id["COSMO_HVD_00_00"]["category"] == "grib_model"
    assert by_id["COMPO_CAPPI.comp.cappi_h5"]["availability"] == "listed_missing"


def test_product_frames_endpoint_returns_parsed_frame_metadata(seeded_products) -> None:
    response = TestClient(app).get("/api/v1/products/COMPO_SRI.comp.sri/frames")
    assert response.status_code == 200
    payload = response.json()
    assert payload["frame_count"] == 4
    assert payload["rendering_status"] == "download_blocked"
    assert payload["renderable"] is None
    assert payload["source"]["url"].endswith("/api/data/product/id/COMPO_SRI.comp.sri")
    assert payload["source"]["retrieved_at"] == "2026-06-30T08:00:00Z"
    assert payload["frames"][0]["frame_time"] == "2026-06-28T03:30:00+00:00"
    assert payload["frames"][-1]["frame_kind"] == "preview"


def test_map_timeline_lists_cached_product_layers(seeded_products) -> None:
    response = TestClient(app).get("/api/v1/map/timeline")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["layers"]) == 2
    layer = next(item for item in payload["layers"] if item["product_id"] == "COMPO_SRI.comp.sri")
    assert layer["frames_renderable"] is False
    assert layer["renderable"] is None
    assert layer["frame_count"] == 4
    assert layer["first_frame_time"] == "2026-06-28T03:30:00+00:00"
    assert "does not currently serve these files publicly" in layer["notes"][1]

    cosmo = next(item for item in payload["layers"] if item["product_id"] == "COSMO_HVD_00_00")
    assert cosmo["frames_renderable"] is True
    assert cosmo["rendering_status"] == "renderable"
    assert cosmo["renderable"]["default_variable"] == "t2m"
    assert cosmo["renderable"]["image_coordinates"][0][0] == pytest.approx(10.963, abs=0.01)
    assert cosmo["renderable"]["attribution"]
    assert cosmo["renderable"]["processed_notice"]


def test_products_endpoint_reports_missing_manifest_fields(seeded_products) -> None:
    response = TestClient(app).get("/api/v1/products")
    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()["products"]}
    assert by_id["COMPO_CAPPI.comp.cappi_h5"]["missing_fields"] == []
    for product in by_id.values():
        assert "missing_fields" in product


def test_products_endpoint_missing_manifest_field_is_reported(monkeypatch, tmp_path) -> None:
    metadata = _source_metadata("product")
    incomplete_payload = [
        {
            "id": "COSMO_HVD_00_00",
            "url": "https://danepubliczne.imgw.pl/api/data/product/id/COSMO_HVD_00_00",
        }
    ]
    parse_result = parse_source("product", incomplete_payload, metadata)
    SourceCache(tmp_path).write_success(
        source_key="product",
        url=metadata.url,
        retrieved_at=metadata.retrieved_at,
        raw_payload=incomplete_payload,
        normalized_payload=[record.model_dump(mode="json") for record in parse_result.records],
        parser_warnings=parse_result.warnings,
    )
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))

    response = TestClient(app).get("/api/v1/products")

    assert response.status_code == 200
    product = response.json()["products"][0]
    assert product["missing_fields"] == ["opis"]


def test_products_endpoint_does_not_synthesize_retrieved_at_for_empty_cache(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))

    response = TestClient(app).get("/api/v1/products")

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrieved_at"] is None
    assert payload["empty_state"]["code"] == "cache_empty"


def test_product_frames_empty_state_without_detail_cache(monkeypatch, tmp_path) -> None:
    _write_cached_source(SourceCache(tmp_path), "product")
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    response = TestClient(app).get("/api/v1/products/COMPO_CAPPI.comp.cappi_h5/frames")
    assert response.status_code == 200
    payload = response.json()
    assert payload["frames"] == []
    assert payload["empty_state"]["code"] == "product_unavailable"


# ---------------------------------------------------------------------------
# Stage 14: renderable frames and the render endpoint
# ---------------------------------------------------------------------------


def _render_settings(tmp_path) -> Settings:
    return Settings(
        cache_dir=tmp_path / "cache",
        geometry_dir=tmp_path / "geometry",
        imgw_base_url="https://danepubliczne.imgw.pl",
    )


@pytest.fixture
def seeded_render_product(tmp_path, monkeypatch) -> Settings:
    settings = _render_settings(tmp_path)
    fixture_path = Path(__file__).parent / "fixtures" / "product_detail" / "COSMO_HVD_00_00.json"
    ProductDetailCache(settings.cache_dir).write_success(
        product_id="COSMO_HVD_00_00",
        url="https://danepubliczne.imgw.pl/api/data/product/id/COSMO_HVD_00_00",
        retrieved_at=datetime.now(UTC),
        files=json.loads(fixture_path.read_text(encoding="utf-8")),
    )
    monkeypatch.setattr(v1, "get_settings", lambda: settings)
    return settings


def _seed_cosmo_binary(settings: Settings, filename: str, *, p1_hours: int) -> None:
    from app.products.rendering import EXPECTED_COSMO_GRID

    j = np.arange(EXPECTED_COSMO_GRID.nj)[:, None]
    i = np.arange(EXPECTED_COSMO_GRID.ni)[None, :]
    values = 270.0 + ((j + i) % 30).astype(np.float64)
    payload = encode_grib1_message(
        values,
        reference_time=(2026, 6, 30, 0, 0),
        p1_hours=p1_hours,
        bits_per_value=16,
    )
    directory = settings.cache_dir.parent / "products" / "binaries" / "COSMO_HVD_00_00"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_bytes(payload)


def test_product_frames_annotate_renderable_state(seeded_render_product) -> None:
    response = TestClient(app).get("/api/v1/products/COSMO_HVD_00_00/frames")
    assert response.status_code == 200
    payload = response.json()
    assert payload["rendering_status"] == "renderable"
    assert payload["renderable"]["default_variable"] == "t2m"
    assert payload["renderable"]["variables"][0]["legend"]
    by_file = {frame["file"]: frame for frame in payload["frames"]}
    lead_zero = by_file["202606300000_202606300000_lfff00000000"]
    assert lead_zero["renderable"] is True
    assert lead_zero["render_ready"] is False
    assert lead_zero["render_url"].endswith(
        "/render/202606300000_202606300000_lfff00000000?variable=t2m"
    )
    assert lead_zero["run_time"] == "2026-06-30T00:00:00+00:00"
    readme = by_file["readme.txt"]
    assert readme["renderable"] is False
    assert readme["renderable_reason"] == "not_a_forecast_frame"


def test_product_frames_stale_flag_reflects_manifest_age(tmp_path, monkeypatch) -> None:
    settings = _render_settings(tmp_path)
    ProductDetailCache(settings.cache_dir).write_success(
        product_id="COSMO_HVD_00_00",
        url="https://danepubliczne.imgw.pl/api/data/product/id/COSMO_HVD_00_00",
        retrieved_at=datetime.now(UTC)
        - timedelta(seconds=settings.product_detail_cache_seconds + 120),
        files=[{"file": "202606300000_202606300000_lfff00000000", "url": "https://x/f"}],
    )
    monkeypatch.setattr(v1, "get_settings", lambda: settings)
    response = TestClient(app).get("/api/v1/products/COSMO_HVD_00_00/frames")
    assert response.status_code == 200
    assert response.json()["stale"] is True


def test_render_endpoint_serves_png_with_frame_metadata(seeded_render_product) -> None:
    _seed_cosmo_binary(
        seeded_render_product, "202606300000_202606300300_lfff00030000", p1_hours=3
    )
    response = TestClient(app).get(
        "/api/v1/products/COSMO_HVD_00_00/render/202606300000_202606300300_lfff00030000",
        params={"variable": "t2m"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert response.headers["x-meteolens-frame-time"] == "2026-06-30T03:00:00+00:00"
    assert response.headers["x-meteolens-run-time"] == "2026-06-30T00:00:00+00:00"
    assert response.headers["x-meteolens-retrieved-at"]

    frames = TestClient(app).get("/api/v1/products/COSMO_HVD_00_00/frames").json()
    frame = next(
        item
        for item in frames["frames"]
        if item["file"] == "202606300000_202606300300_lfff00030000"
    )
    assert frame["render_ready"] is True


def test_render_endpoint_rejects_non_renderable_product(seeded_render_product) -> None:
    response = TestClient(app).get(
        "/api/v1/products/COMPO_SRI.comp.sri/render/2026062803300000dBR.sri"
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "not_renderable"


def test_render_endpoint_missing_frame_and_manifest(tmp_path, monkeypatch) -> None:
    settings = _render_settings(tmp_path)
    monkeypatch.setattr(v1, "get_settings", lambda: settings)
    client = TestClient(app)

    no_manifest = client.get(
        "/api/v1/products/COSMO_HVD_00_00/render/202606300000_202606300000_lfff00000000"
    )
    assert no_manifest.status_code == 503
    assert no_manifest.json()["detail"]["error"]["code"] == "cache_empty"

    ProductDetailCache(settings.cache_dir).write_success(
        product_id="COSMO_HVD_00_00",
        url="https://danepubliczne.imgw.pl/api/data/product/id/COSMO_HVD_00_00",
        retrieved_at=datetime.now(UTC),
        files=[{"file": "202606300000_202606300000_lfff00000000", "url": "https://x/f"}],
    )
    unknown_frame = client.get(
        "/api/v1/products/COSMO_HVD_00_00/render/202606300000_202606309900_lfff00990000"
    )
    assert unknown_frame.status_code == 404
    assert unknown_frame.json()["detail"]["error"]["code"] == "frame_missing"
