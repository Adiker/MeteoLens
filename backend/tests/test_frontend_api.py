import csv
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

import app.api.v1 as v1
from app.core.config import Settings
from app.imgw.cache import SourceCache
from app.imgw.parsers import parse_source
from app.main import app
from app.normalization.models import SourceMetadata
from tests.settings_helpers import apply_test_settings
from tests.test_parsers import load_fixture


def _settings(tmp_path) -> Settings:
    db_path = tmp_path / "meteolens.sqlite3"
    return Settings(
        cache_dir=tmp_path,
        # Isolate tests from any reviewed datasets imported into the real
        # data/geometry directory of this checkout.
        geometry_dir=tmp_path / "geometry",
        database_url=f"sqlite:///{db_path}",
        imgw_base_url="https://danepubliczne.imgw.pl",
    )


def _geometry_fixture_settings(tmp_path) -> Settings:
    db_path = tmp_path / "meteolens.sqlite3"
    return Settings(
        cache_dir=tmp_path,
        geometry_dir=Path(__file__).parent / "fixtures" / "geometry",
        database_url=f"sqlite:///{db_path}",
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


def _seed_cache(tmp_path, source_keys: tuple[str, ...]) -> SourceCache:
    cache = SourceCache(tmp_path)
    for source_key in source_keys:
        _write_cached_source(cache, source_key)
    return cache


def test_stations_returns_empty_state_when_cache_is_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/stations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stations"] == []
    assert payload["empty_state"]["code"] == "cache_empty"
    assert payload["cache"][0]["status"]["status"] == "empty"


def test_stations_detail_and_observations_use_normalized_cache(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    list_response = TestClient(app).get("/api/v1/stations?type=hydro&q=Przewo")
    detail_response = TestClient(app).get("/api/v1/stations/hydro:151140030")
    observations_response = TestClient(app).get(
        "/api/v1/stations/hydro:151140030/observations?metric=water_level"
    )

    assert list_response.status_code == 200
    assert list_response.json()["stations"][0]["source"]["provider"] == "IMGW-PIB"
    assert list_response.json()["stations"][0]["missing_fields"] == [
        "temperatura_wody",
        "temperatura_wody_data_pomiaru",
    ]
    assert detail_response.status_code == 200
    assert detail_response.json()["station"]["raw"]["id_stacji"] == "151140030"
    assert observations_response.status_code == 200
    observations = observations_response.json()["observations"]
    assert len(observations) == 1
    assert observations[0]["metric"] == "water_level"
    assert observations[0]["data_delay_seconds"] is not None


def test_stations_filter_miss_returns_matching_empty_state(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/stations?type=synop")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stations"] == []
    assert payload["empty_state"]["code"] == "no_matching_records"


def test_stations_serve_stale_cache_after_refresh_error(monkeypatch, tmp_path) -> None:
    cache = _seed_cache(tmp_path, ("hydro",))
    cache.write_error(source_key="hydro", error="timeout")
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/stations?type=hydro")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stations"][0]["id"] == "hydro:151140030"
    assert payload["empty_state"] is None
    hydro_cache = next(state for state in payload["cache"] if state["source_key"] == "hydro")
    assert hydro_cache["status"]["status"] == "stale"
    assert hydro_cache["status"]["error"] == "timeout"


def test_observations_accept_naive_datetime_filters(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get(
        "/api/v1/stations/hydro:151140030/observations"
        "?metric=water_level&from=2026-06-30T05:00:00"
    )

    assert response.status_code == 200
    assert len(response.json()["observations"]) == 1


def test_warnings_filters_preserve_area_metadata(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("warningsmeteo", "warningshydro"))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

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
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get(
        "/api/v1/map/layers?layers=synop_stations,hydro_stations,warnings_meteo"
    )

    assert response.status_code == 200
    layers = {layer["key"]: layer for layer in response.json()["layers"]}
    assert layers["hydro_stations"]["geojson"]["features"][0]["geometry"]["type"] == "Point"
    assert layers["synop_stations"]["geojson"]["features"] == []
    assert layers["synop_stations"]["missing_geometry"][0]["reason"] == "missing_lat_lon"
    assert layers["warnings_meteo"]["records"][0]["area_codes"] == ["1205", "1207", "2461"]
    assert layers["warnings_meteo"]["missing_geometry"]
    assert layers["warnings_meteo"]["missing_geometry"][0]["reason"] in {
        "missing_area_geometry_dataset",
        "geometry_not_found",
    }


def test_location_summary_distinguishes_missing_coords_from_empty_cache(
    monkeypatch, tmp_path
) -> None:
    _seed_cache(tmp_path, ("synop",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/location/summary?lat=52.23&lon=21.01&radius_km=50")

    assert response.status_code == 200
    payload = response.json()
    assert payload["nearest_stations"] == []
    assert payload["empty_state"]["code"] == "no_location_data"


def test_location_summary_returns_nearest_cached_stations(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro", "meteo", "warningsmeteo"))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/location/summary?lat=51.52&lon=14.82&radius_km=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["nearest_stations"][0]["id"] == "hydro:151140030"
    assert payload["cache"]
    assert isinstance(payload["notes"], list)


def test_station_exports_include_attribution_and_missing_fields(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    csv_response = TestClient(app).get("/api/v1/export/station/hydro:151140030.csv")
    json_response = TestClient(app).get("/api/v1/export/station/hydro:151140030.json")

    assert csv_response.status_code == 200
    assert "Źródło danych: IMGW-PIB." in csv_response.text
    assert "temperatura_wody" in csv_response.text
    assert "None" not in csv_response.text.splitlines()[1]
    assert json_response.status_code == 200
    payload = json_response.json()
    assert payload["attribution"] == "Źródło danych: IMGW-PIB."
    assert payload["processed_notice"] == "Dane IMGW-PIB zostały przetworzone przez MeteoLens."
    assert payload["station"]["id"] == "hydro:151140030"


def test_station_csv_export_distinguishes_real_zero_from_missing(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("synop",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))
    client = TestClient(app)

    zero_response = client.get("/api/v1/export/station/synop:12295.csv")
    missing_response = client.get("/api/v1/export/station/synop:12550.csv")

    assert zero_response.status_code == 200
    zero_rows = {row["metric"]: row for row in csv.DictReader(zero_response.text.splitlines())}
    # suma_opadu ("0") is a genuine zero measurement — never blank it out.
    assert zero_rows["precipitation_sum"]["value"] == "0.0"
    assert zero_rows["precipitation_sum"]["missing"] == "False"

    assert missing_response.status_code == 200
    missing_rows = {
        row["metric"]: row for row in csv.DictReader(missing_response.text.splitlines())
    }
    # cisnienie is null in this row — it must stay an explicit empty cell,
    # never a "0" that would misrepresent a real reading.
    assert missing_rows["pressure"]["value"] == ""
    assert missing_rows["pressure"]["missing"] == "True"


def test_warning_geojson_export_includes_attribution_and_missing_geometry(
    monkeypatch,
    tmp_path,
) -> None:
    _seed_cache(tmp_path, ("warningsmeteo",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/export/warnings.geojson?type=meteo&level=2")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/geo+json")
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["attribution"] == "Źródło danych: IMGW-PIB."
    assert payload["processed_notice"] == "Dane IMGW-PIB zostały przetworzone przez MeteoLens."
    assert payload["non_spatial_records"][0]["area_codes"] == ["1205", "1207", "2461"]
    assert payload["missing_geometry"][0]["reason"] in {
        "missing_area_geometry_dataset",
        "geometry_not_found",
    }


def test_map_state_export_records_visible_layers_and_cache(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro", "warningsmeteo"))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get(
        "/api/v1/export/map-state.json"
        "?layers=hydro_stations,warnings_meteo"
        "&lng=19.1&lat=52.2&zoom=6&mode=expert&warning_level=2"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_layers"] == ["hydro_stations", "warnings_meteo"]
    assert payload["view"] == {
        "lng": 19.1,
        "lat": 52.2,
        "zoom": 6.0,
        "bbox": None,
    }
    assert payload["filters"]["warning_level"] == 2
    assert payload["attribution"] == "Źródło danych: IMGW-PIB."
    assert payload["processed_notice"] == "Dane IMGW-PIB zostały przetworzone przez MeteoLens."
    assert {summary["key"] for summary in payload["layer_summaries"]} == {
        "hydro_stations",
        "warnings_meteo",
    }
    assert payload["cache"]


def test_map_layers_rejects_unsupported_layer_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/map/layers?layers=not_a_real_layer")

    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "unsupported_layer"


def test_map_layers_rejects_invalid_bbox_format(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/map/layers?bbox=not,a,bbox")

    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "invalid_filter"


def test_map_layers_rejects_bbox_with_min_above_max(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/map/layers?bbox=20,50,10,55")

    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "invalid_filter"


def test_map_layers_bbox_excludes_stations_outside_area(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get(
        "/api/v1/map/layers?layers=hydro_stations&bbox=0,0,1,1"
    )

    assert response.status_code == 200
    layer = response.json()["layers"][0]
    assert layer["geojson"]["features"] == []


def test_map_layers_report_cache_empty_when_no_data_cached(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/map/layers?layers=hydro_stations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["empty_state"]["code"] == "cache_empty"


def test_stations_bbox_and_query_filters_exclude_non_matches(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    bbox_miss = TestClient(app).get("/api/v1/stations?type=hydro&bbox=0,0,1,1")
    query_miss = TestClient(app).get("/api/v1/stations?type=hydro&q=NoSuchStation")
    bbox_hit = TestClient(app).get("/api/v1/stations?type=hydro&bbox=10,50,20,55")

    assert bbox_miss.json()["stations"] == []
    assert query_miss.json()["stations"] == []
    assert bbox_hit.json()["stations"][0]["id"] == "hydro:151140030"


def test_stations_bbox_filter_excludes_stations_without_coordinates(
    monkeypatch, tmp_path
) -> None:
    _seed_cache(tmp_path, ("synop",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/stations?type=synop&bbox=10,50,20,55")

    assert response.json()["stations"] == []


def test_observations_missing_timestamp_excluded_by_time_range_filter(
    monkeypatch, tmp_path
) -> None:
    _seed_cache(tmp_path, ("hydro",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get(
        "/api/v1/stations/hydro:151140030/observations"
        "?metric=water_temperature&from=2026-06-30T00:00:00"
    )

    assert response.json()["observations"] == []


def test_station_not_found_returns_404_when_cache_has_other_stations(
    monkeypatch, tmp_path
) -> None:
    _seed_cache(tmp_path, ("hydro",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/stations/hydro:does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "not_found"


def test_station_returns_503_when_cache_is_completely_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/stations/hydro:151140030")

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "cache_empty"


def test_warning_not_found_returns_404_when_cache_has_other_warnings(
    monkeypatch, tmp_path
) -> None:
    _seed_cache(tmp_path, ("warningsmeteo",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/warnings/warningsmeteo:does-not-exist")

    assert response.status_code == 404


def test_warning_returns_503_when_cache_is_completely_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/warnings/warningsmeteo:does-not-exist")

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "cache_empty"


def test_observations_filters_by_metric_and_time_range(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro",))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    wrong_metric = TestClient(app).get(
        "/api/v1/stations/hydro:151140030/observations?metric=flow"
        "&from=2026-06-30T05:00:00&to=2026-06-30T09:00:00"
    )
    before_range = TestClient(app).get(
        "/api/v1/stations/hydro:151140030/observations?metric=water_level"
        "&from=2026-06-30T08:00:00"
    )
    after_range = TestClient(app).get(
        "/api/v1/stations/hydro:151140030/observations?metric=water_level"
        "&to=2026-06-30T06:00:00"
    )
    exact_match = TestClient(app).get(
        "/api/v1/stations/hydro:151140030/observations?metric=water_level"
        "&from=2026-06-30T07:00:00&to=2026-06-30T07:00:00"
    )

    assert wrong_metric.json()["observations"] == []
    assert before_range.json()["observations"] == []
    assert after_range.json()["observations"] == []
    assert len(exact_match.json()["observations"]) == 1


def test_warnings_filters_exclude_by_level_phenomenon_basin_and_active_at(
    monkeypatch, tmp_path
) -> None:
    _seed_cache(tmp_path, ("warningsmeteo", "warningshydro"))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    client = TestClient(app)
    level_miss = client.get("/api/v1/warnings?type=meteo&level=1")
    phenomenon_miss = client.get("/api/v1/warnings?phenomenon=Powodz")
    teryt_miss = client.get("/api/v1/warnings?teryt=9999")
    basin_miss = client.get("/api/v1/warnings?basin=NOT_A_BASIN")
    before_valid_from = client.get(
        "/api/v1/warnings?type=meteo&active_at=2026-06-30T10:00:00"
    )
    after_valid_to = client.get(
        "/api/v1/warnings?type=meteo&active_at=2100-01-01T00:00:00"
    )
    active_hit = client.get(
        "/api/v1/warnings?type=meteo&active_at=2026-06-30T15:00:00&phenomenon=Burze"
        "&teryt=1205&level=2"
    )
    basin_hit = client.get("/api/v1/warnings?basin=Z_P_WP_1856")

    assert level_miss.json()["warnings"] == []
    assert phenomenon_miss.json()["warnings"] == []
    assert teryt_miss.json()["warnings"] == []
    assert basin_miss.json()["warnings"] == []
    assert before_valid_from.json()["warnings"] == []
    assert after_valid_to.json()["warnings"] == []
    assert len(active_hit.json()["warnings"]) == 1
    assert len(basin_hit.json()["warnings"]) == 1


def test_cache_read_error_returns_503_cache_invalid(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro",))
    (tmp_path / "hydro.json").write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/stations?type=hydro")

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "cache_invalid"


def test_cache_with_malformed_normalized_record_returns_503_cache_invalid(
    monkeypatch, tmp_path
) -> None:
    cache = _seed_cache(tmp_path, ("hydro",))
    payload = cache.read("hydro")
    cache.write_success(
        source_key="hydro",
        url=payload.url,
        retrieved_at=payload.retrieved_at,
        raw_payload=payload.raw_payload,
        normalized_payload=[{"kind": "station", "not": "a valid station"}],
        parser_warnings=[],
    )
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/stations?type=hydro")

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "cache_invalid"


def test_map_geojson_export_includes_non_spatial_warning_records(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("hydro", "warningsmeteo"))
    monkeypatch.setattr(v1, "get_settings", lambda: _settings(tmp_path))
    apply_test_settings(monkeypatch, _settings(tmp_path))

    response = TestClient(app).get("/api/v1/export/map.geojson")

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["features"][0]["id"] == "hydro:151140030"
    assert payload["non_spatial_records"][0]["id"] == "warningsmeteo:Sk20260630043222424"
    assert payload["attribution"] == "Źródło danych: IMGW-PIB."
    assert payload["geometry_attributions"] == []
    assert payload["processed_notice"] == "Dane IMGW-PIB zostały przetworzone przez MeteoLens."


def test_map_geojson_export_includes_geometry_attribution(monkeypatch, tmp_path) -> None:
    _seed_cache(tmp_path, ("warningsmeteo",))
    settings = _geometry_fixture_settings(tmp_path)
    monkeypatch.setattr(v1, "get_settings", lambda: settings)
    apply_test_settings(monkeypatch, settings)

    response = TestClient(app).get("/api/v1/export/map.geojson?layers=warnings_meteo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["features"][0]["properties"]["dataset_key"] == "teryt_counties"
    assert payload["geometry_attributions"] == ["MeteoLens test fixture"]
