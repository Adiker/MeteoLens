from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

import app.services.observation_history as history_service
from app.core.config import Settings
from app.db.engine import init_db, reset_engine_cache
from app.imgw.cache import SourceCache
from app.imgw.parsers import parse_source
from app.main import app
from app.normalization.models import SourceMetadata, Station
from tests.settings_helpers import apply_test_settings
from tests.test_parsers import load_fixture


def _settings(tmp_path: Path) -> Settings:
    db_path = tmp_path / "history.sqlite3"
    return Settings(
        cache_dir=tmp_path / "cache",
        database_url=f"sqlite:///{db_path}",
        imgw_base_url="https://danepubliczne.imgw.pl",
    )


def _prepare(tmp_path: Path, monkeypatch) -> None:
    reset_engine_cache()
    settings = _settings(tmp_path)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    apply_test_settings(monkeypatch, settings)
    init_db()


def _seed_station_cache(cache: SourceCache, source_key: str = "hydro") -> Station:
    metadata = SourceMetadata(
        source_key=source_key,
        url=f"https://danepubliczne.imgw.pl/api/data/{source_key}",
        retrieved_at=datetime(2026, 6, 30, 7, 30, tzinfo=UTC),
    )
    parse_result = parse_source(source_key, load_fixture(source_key), metadata)
    cache.write_success(
        source_key=source_key,
        url=metadata.url,
        retrieved_at=metadata.retrieved_at,
        raw_payload=load_fixture(source_key),
        normalized_payload=[record.model_dump(mode="json") for record in parse_result.records],
        parser_warnings=parse_result.warnings,
    )
    station = next(record for record in parse_result.records if isinstance(record, Station))
    history_service.persist_station(station)
    return station


def test_observations_endpoint_returns_history_when_available(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    station = _seed_station_cache(SourceCache(_settings(tmp_path).cache_dir))

    response = TestClient(app).get(
        f"/api/v1/stations/{station.id}/observations?metric=water_level"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["series_kind"] == "history"
    assert len(payload["observations"]) == 1
    assert payload["observations"][0]["metric"] == "water_level"
    assert payload["observations"][0]["missing"] is False


def test_rankings_returns_highest_water_level(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    _seed_station_cache(SourceCache(_settings(tmp_path).cache_dir))

    response = TestClient(app).get(
        "/api/v1/rankings?metric=water_level&direction=highest&type=hydro"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["rankings"]
    assert payload["rankings"][0]["metric"] == "water_level"
    assert payload["processed_notice"]


def test_compare_requires_known_station_ids(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    station = _seed_station_cache(SourceCache(_settings(tmp_path).cache_dir))

    response = TestClient(app).get(
        "/api/v1/stations/compare"
        f"?station_ids={station.id}&metric=water_level"
    )

    assert response.status_code == 200
    assert station.id in response.json()["series"]


def test_observation_history_export_csv_includes_series_metadata(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    station = _seed_station_cache(SourceCache(_settings(tmp_path).cache_dir))

    response = TestClient(app).get(
        f"/api/v1/export/station/{station.id}/observations.csv?metric=water_level"
    )

    assert response.status_code == 200
    body = response.text
    assert "series_kind" in body.splitlines()[0]
    assert "water_level" in body
    assert "IMGW-PIB" in body
