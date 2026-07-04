from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import app.api.v1 as v1
from app.core.config import Settings
from app.imgw.cache import SourceCache
from app.imgw.parsers import parse_source
from app.main import app
from app.normalization.models import SourceMetadata
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


@pytest.fixture
def seeded_cache(tmp_path, monkeypatch):
    cache = SourceCache(tmp_path)
    for source_key in ("hydro", "warningsmeteo"):
        _write_cached_source(cache, source_key)
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    return tmp_path


def test_freshness_endpoint_reports_source_status(seeded_cache) -> None:
    response = TestClient(app).get("/api/v1/status/freshness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] in {"healthy", "stale", "degraded"}
    assert len(payload["sources"]) >= 6
    assert payload["alerting_disclaimer"]
    hydro = next(item for item in payload["sources"] if item["source_key"] == "hydro")
    assert hydro["record_count"] == 1


def test_freshness_counts_stale_cache_with_fetch_error_as_degraded(
    tmp_path, monkeypatch
) -> None:
    cache = SourceCache(tmp_path)
    _write_cached_source(cache, "hydro")
    cache.write_error(source_key="hydro", error="upstream timeout")
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))

    response = TestClient(app).get("/api/v1/status/freshness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] == "degraded"
    assert any("fetch errors" in note for note in payload["notes"])
    hydro = next(item for item in payload["sources"] if item["source_key"] == "hydro")
    assert hydro["cache_status"] == "stale"
    assert hydro["error"] == "upstream timeout"


def test_compare_warning_station_returns_observations_and_warnings(seeded_cache) -> None:
    response = TestClient(app).get("/api/v1/compare/warning-station/hydro:151140030")
    assert response.status_code == 200
    payload = response.json()
    assert payload["station"]["id"] == "hydro:151140030"
    assert isinstance(payload["observations"], list)
    assert isinstance(payload["warnings"], list)
    assert payload["alerting_disclaimer"]
