import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.api.v1 as v1
from app.core.config import Settings
from app.imgw.cache import SourceCache
from app.imgw.parsers import parse_source
from app.main import app
from app.normalization.models import SourceMetadata
from app.products.detail_cache import ProductDetailCache
from tests.test_parsers import load_fixture


def _settings(tmp_path) -> Settings:
    return Settings(cache_dir=tmp_path, imgw_base_url="https://danepubliczne.imgw.pl")


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
    assert payload["research_date"] == "2026-07-01"
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
    assert payload["rendering_status"] == "parser_not_implemented"
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
    assert layer["frame_count"] == 4
    assert layer["first_frame_time"] == "2026-06-28T03:30:00+00:00"
    assert "Binary product parsing" in layer["notes"][1]


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
