from datetime import UTC, datetime

from fastapi.testclient import TestClient

import app.api.v1 as v1
from app.core.config import Settings
from app.imgw.cache import SourceCache
from app.imgw.parsers import parse_source
from app.main import app
from app.normalization.models import SourceMetadata
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


def _seed_cache(tmp_path, source_keys: tuple[str, ...]) -> SourceCache:
    cache = SourceCache(tmp_path)
    for source_key in source_keys:
        _write_cached_source(cache, source_key)
    return cache


def test_stations_returns_empty_state_when_cache_is_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))

    response = TestClient(app).get("/api/v1/stations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stations"] == []
    assert payload["empty_state"]["code"] == "cache_empty"
    assert payload["cache"][0]["status"]["status"] == "empty"


def test_stations_detail_and_observations_use_normalized_cache(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))

    list_response = TestClient(app).get("/api/v1/stations?type=hydro&q=Przewo")
    detail_response = TestClient(app).get("/api/v1/stations/hydro:151140030")
    observations_response = TestClient(app).get(
        "/api/v1/stations/hydro:151140030/observations?metric=water_level"
    )

    assert list_response.status_code == 200
    assert list_response.json()["stations"][0]["source"]["provider"] == "IMGW-PIB"
    assert list_response.json()["stations"][0]["missing_fields"] == ["temperatura_wody"]
    assert detail_response.status_code == 200
    assert detail_response.json()["station"]["raw"]["id_stacji"] == "151140030"
    assert observations_response.status_code == 200
    observations = observations_response.json()["observations"]
    assert len(observations) == 1
    assert observations[0]["metric"] == "water_level"
    assert observations[0]["data_delay_seconds"] is not None


def test_warnings_filters_preserve_area_metadata(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("warningsmeteo", "warningshydro"))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))

    response = TestClient(app).get("/api/v1/warnings?type=meteo&teryt=1205&level=2")
    detail_response = TestClient(app).get("/api/v1/warnings/warningsmeteo:Sk20260630043222424")

    assert response.status_code == 200
    payload = response.json()
    assert payload["warnings"][0]["area_codes"] == ["1205", "1207", "2461"]
    assert payload["warnings"][0]["source"]["attribution"] == "Źródło danych: IMGW-PIB."
    assert detail_response.status_code == 200
    assert detail_response.json()["geometry_status"] == "missing_area_geometry_dataset"


def test_map_layers_include_points_and_missing_geometry(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("synop", "hydro", "meteo", "warningsmeteo"))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))

    response = TestClient(app).get(
        "/api/v1/map/layers?layers=synop_stations,hydro_stations,warnings_meteo"
    )

    assert response.status_code == 200
    layers = {layer["key"]: layer for layer in response.json()["layers"]}
    assert layers["hydro_stations"]["geojson"]["features"][0]["geometry"]["type"] == "Point"
    assert layers["synop_stations"]["geojson"]["features"] == []
    assert layers["synop_stations"]["missing_geometry"][0]["reason"] == "missing_lat_lon"
    assert layers["warnings_meteo"]["records"][0]["area_codes"] == ["1205", "1207", "2461"]
    assert layers["warnings_meteo"]["missing_geometry"][0]["reason"] == (
        "missing_area_geometry_dataset"
    )


def test_location_summary_returns_nearest_cached_stations(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro", "meteo", "warningsmeteo"))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))

    response = TestClient(app).get("/api/v1/location/summary?lat=51.52&lon=14.82&radius_km=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["nearest_stations"][0]["id"] == "hydro:151140030"
    assert payload["notes"]


def test_station_exports_include_attribution_and_missing_fields(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))

    csv_response = TestClient(app).get("/api/v1/export/station/hydro:151140030.csv")
    json_response = TestClient(app).get("/api/v1/export/station/hydro:151140030.json")

    assert csv_response.status_code == 200
    assert "Źródło danych: IMGW-PIB." in csv_response.text
    assert "temperatura_wody" in csv_response.text
    assert json_response.status_code == 200
    payload = json_response.json()
    assert payload["processed_notice"] == "Dane IMGW-PIB zostały przetworzone przez MeteoLens."
    assert payload["station"]["id"] == "hydro:151140030"


def test_map_geojson_export_includes_non_spatial_warning_records(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro", "warningsmeteo"))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))

    response = TestClient(app).get("/api/v1/export/map.geojson")

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["features"][0]["id"] == "hydro:151140030"
    assert payload["non_spatial_records"][0]["id"] == "warningsmeteo:Sk20260630043222424"
    assert payload["processed_notice"] == "Dane IMGW-PIB zostały przetworzone przez MeteoLens."
