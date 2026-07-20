from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.geometry.loader import GeometryFeature, get_geometry_store, reset_geometry_store
from app.geometry.spatial import find_area_geometry, point_in_geometry, resolve_warning_geometries
from app.imgw.cache import SourceCache
from app.imgw.parsers import parse_source
from app.main import app
from app.normalization.models import SourceMetadata, Warning, WarningArea
from tests.settings_helpers import apply_test_settings
from tests.test_frontend_api import _seed_cache
from tests.test_parsers import load_fixture, source_metadata


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


def test_map_layers_bbox_excludes_warning_polygons_outside_view(
    monkeypatch, tmp_path
) -> None:
    _prepare(tmp_path, monkeypatch)
    _seed_cache(tmp_path, ("warningsmeteo",))

    response = TestClient(app).get(
        "/api/v1/map/layers?layers=warnings_meteo&bbox=0,0,1,1"
    )

    assert response.status_code == 200
    layer = response.json()["layers"][0]
    assert layer["geojson"]["features"] == []
    assert layer["records"] == []


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


def test_map_layers_exclude_expired_warnings(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    cache = SourceCache(tmp_path)
    metadata = SourceMetadata(
        source_key="warningsmeteo",
        url="https://danepubliczne.imgw.pl/api/data/warningsmeteo",
        retrieved_at=datetime(2020, 1, 2, 0, 0, tzinfo=UTC),
    )
    expired_payload = [
        {
            "id": "expired-1",
            "nazwa_zdarzenia": "Burze",
            "stopien": "2",
            "prawdopodobienstwo": "70",
            "obowiazuje_do": "2020-01-01 23:59:59",
            "obowiazuje_od": "2020-01-01 00:00:00",
            "opublikowano": "2020-01-01 00:00:00",
            "tresc": "Prognozowane są burze.",
            "komentarz": "Brak.",
            "biuro": "Centralne Biuro Prognoz Meteorologicznych w Warszawie",
            "teryt": ["1205"],
        }
    ]
    parse_result = parse_source("warningsmeteo", expired_payload, metadata)
    cache.write_success(
        source_key="warningsmeteo",
        url=metadata.url,
        retrieved_at=metadata.retrieved_at,
        raw_payload=expired_payload,
        normalized_payload=[record.model_dump(mode="json") for record in parse_result.records],
        parser_warnings=parse_result.warnings,
    )

    response = TestClient(app).get("/api/v1/map/layers?layers=warnings_meteo")

    assert response.status_code == 200
    layer = response.json()["layers"][0]
    assert layer["geojson"]["features"] == []
    assert layer["records"] == []


def test_find_area_geometry_keeps_missing_county_unresolved(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    store = get_geometry_store()

    # "1299" is not in the county dataset; only its two-digit prefix ("12") is a
    # real voivodeship. It must stay unresolved rather than expanding to the
    # whole voivodeship geometry.
    missing_county = find_area_geometry(store, WarningArea(area_type="teryt", code="1299"))
    assert missing_county is None

    real_voivodeship = find_area_geometry(store, WarningArea(area_type="teryt", code="12"))
    assert real_voivodeship is not None
    assert real_voivodeship.dataset_key == "teryt_voivodeships"


def test_location_summary_keeps_unresolved_fallback_alongside_polygon_match(
    monkeypatch, tmp_path
) -> None:
    _prepare(tmp_path, monkeypatch)
    cache = _seed_cache(tmp_path, ("warningsmeteo",))
    metadata = SourceMetadata(
        source_key="warningshydro",
        url="https://danepubliczne.imgw.pl/api/data/warningshydro",
        retrieved_at=datetime(2026, 6, 30, 7, 30, tzinfo=UTC),
    )
    # A hydro warning whose basin has no matching geometry in the store, so it
    # can never be a polygon match and must fall back with geometry_status
    # other than "resolved".
    unresolved_payload = [
        {
            "numer": "hydro-warning-1",
            "zdarzenie": "Wezbranie",
            "stopień": "1",
            "prawdopodobienstwo": "60",
            "data_od": "2026-06-30 00:00:00",
            "data_do": "2099-12-31 23:59:59",
            "opublikowano": "2026-06-30 00:00:00",
            "biuro": "Biuro Prognoz Hydrologicznych",
            "komentarz": "Brak.",
            "obszary": [
                {
                    "wojewodztwo": None,
                    "opis": "Zlewnia testowa",
                    "kod_zlewni": ["no-such-basin"],
                }
            ],
        }
    ]
    parse_result = parse_source("warningshydro", unresolved_payload, metadata)
    cache.write_success(
        source_key="warningshydro",
        url=metadata.url,
        retrieved_at=metadata.retrieved_at,
        raw_payload=unresolved_payload,
        normalized_payload=[record.model_dump(mode="json") for record in parse_result.records],
        parser_warnings=parse_result.warnings,
    )

    response = TestClient(app).get(
        "/api/v1/location/summary?lat=50.5&lon=19.0&radius_km=50"
    )

    assert response.status_code == 200
    warnings = response.json()["warnings"]
    match_types = {warning["id"]: warning.get("match_type") for warning in warnings}
    assert match_types.get("warningsmeteo:Sk20260630043222424") == "polygon"
    hydro_id = "warningshydro:hydro-warning-1:2026-06-30 00:00:00"
    assert hydro_id in match_types
    assert match_types[hydro_id] != "polygon"


def test_hydro_basin_alias_and_primary_codes_resolve(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    store = get_geometry_store()

    primary = find_area_geometry(store, WarningArea(area_type="basin", code="Z_P_WP_1856"))
    alias = find_area_geometry(store, WarningArea(area_type="basin", code="R_P_WP_1856"))
    coastal = find_area_geometry(store, WarningArea(area_type="basin", code="W_G_PM_0_A"))

    assert primary is not None
    assert alias is not None
    assert primary.code == alias.code
    assert coastal is None


def test_hydro_warning_geometry_status_distinguishes_unmatched_from_missing_dataset(
    monkeypatch, tmp_path
) -> None:
    _prepare(tmp_path, monkeypatch)
    store = get_geometry_store()
    hydro = parse_source(
        "warningshydro",
        load_fixture("warningshydro"),
        source_metadata("warningshydro"),
    ).records[0]
    assert isinstance(hydro, Warning)

    resolved = resolve_warning_geometries(hydro, store)
    assert resolved["geometry_status"] == "resolved"
    assert resolved["resolved_areas"][0]["code"] == "Z_P_WP_1856"

    coastal = Warning(
        kind="warning",
        id="warningshydro:coastal",
        source_id="coastal",
        source_key="warningshydro",
        warning_type="hydro",
        event="Wezbranie sztormowe",
        level=1,
        probability=None,
        valid_from=None,
        valid_to=None,
        published_at=None,
        office=None,
        content=None,
        comment=None,
        areas=[WarningArea(area_type="basin", code="W_G_PM_0_A", label="morze")],
        missing_fields=[],
        source=hydro.source,
        raw={},
    )
    unmatched = resolve_warning_geometries(coastal, store)
    assert unmatched["geometry_status"] == "geometry_not_found"
    assert unmatched["unresolved_areas"][0]["reason"] == "geometry_not_found"
    assert "hydro_basins" in unmatched["unresolved_areas"][0]["dataset_keys"]


def test_map_layers_include_hydro_warning_polygons(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    _seed_cache(tmp_path, ("warningshydro",))

    response = TestClient(app).get("/api/v1/map/layers?layers=warnings_hydro")

    assert response.status_code == 200
    layer = response.json()["layers"][0]
    assert layer["geojson"]["features"]
    assert layer["geojson"]["features"][0]["geometry"]["type"] == "Polygon"
    assert layer["records"][0]["geometry_status"] == "resolved"


def test_location_summary_polygon_matches_hydro_basin(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    _seed_cache(tmp_path, ("warningshydro",))

    # Fixture basin polygon covers lon 16-18, lat 52-53.5.
    response = TestClient(app).get(
        "/api/v1/location/summary?lat=52.5&lon=17.0&radius_km=50"
    )

    assert response.status_code == 200
    warnings = response.json()["warnings"]
    assert warnings
    assert warnings[0]["match_type"] == "polygon"
    assert warnings[0]["source_key"] == "warningshydro"


def test_point_in_geometry_excludes_polygon_holes() -> None:
    feature = GeometryFeature(
        id="test",
        code="test",
        label=None,
        geometry_type="Polygon",
        coordinates=[
            [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
            [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]],
        ],
        source_file="test.geojson",
        dataset_key="test",
    )

    assert point_in_geometry(0.5, 0.5, feature) is True
    assert point_in_geometry(2.0, 2.0, feature) is False
