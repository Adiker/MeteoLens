from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.geometry.loader import reset_geometry_store
from app.main import app
from tests.settings_helpers import apply_test_settings
from tests.test_frontend_api import _seed_cache


def _geometry_settings(tmp_path: Path) -> Settings:
    geometry_dir = Path(__file__).parent / "fixtures" / "geometry"
    return Settings(
        cache_dir=tmp_path,
        geometry_dir=geometry_dir,
        imgw_base_url="https://danepubliczne.imgw.pl",
    )


def _prepare(tmp_path, monkeypatch) -> None:
    reset_geometry_store()
    apply_test_settings(monkeypatch, _geometry_settings(tmp_path))


def test_geometry_datasets_endpoint_lists_loaded_fixtures(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)

    response = TestClient(app).get("/api/v1/geometry/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["manifest_present"] is True
    keys = {item["key"] for item in payload["datasets"]}
    assert "teryt_counties" in keys
    assert payload["datasets"][0]["feature_count"] >= 1


def test_map_layers_include_warning_polygons_when_geometry_exists(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    _seed_cache(tmp_path, ("warningsmeteo",))

    response = TestClient(app).get("/api/v1/map/layers?layers=warnings_meteo")

    assert response.status_code == 200
    layer = response.json()["layers"][0]
    assert len(layer["geojson"]["features"]) >= 1
    assert layer["geojson"]["features"][0]["geometry"]["type"] == "Polygon"


def test_warnings_support_county_filter(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    _seed_cache(tmp_path, ("warningsmeteo",))

    response = TestClient(app).get("/api/v1/warnings?county=1205")

    assert response.status_code == 200
    assert len(response.json()["warnings"]) == 1


def test_location_summary_polygon_matches_point(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    _seed_cache(tmp_path, ("warningsmeteo",))

    response = TestClient(app).get(
        "/api/v1/location/summary?lat=50.5&lon=19.0&radius_km=50"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["warnings"]
    assert payload["warnings"][0]["match_type"] == "polygon"
