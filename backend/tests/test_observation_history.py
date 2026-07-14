from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

import app.services.observation_history as history_service
from app.core.config import Settings
from app.db.engine import get_engine, init_db, reset_engine_cache
from app.db.repository import ObservationRepository
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
        geometry_dir=tmp_path / "geometry",
        database_url=f"sqlite:///{db_path}",
        imgw_base_url="https://danepubliczne.imgw.pl",
    )


def _prepare(tmp_path: Path, monkeypatch) -> None:
    reset_engine_cache()
    settings = _settings(tmp_path)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    apply_test_settings(monkeypatch, settings)
    init_db()


def test_init_db_migrates_legacy_history_before_origin_index(monkeypatch, tmp_path) -> None:
    reset_engine_cache()
    settings = _settings(tmp_path)
    apply_test_settings(monkeypatch, settings)
    connection = get_engine()
    connection.executescript(
        """
        CREATE TABLE observation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id TEXT NOT NULL,
            station_name TEXT NOT NULL,
            source_key TEXT NOT NULL,
            station_type TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            unit TEXT,
            observed_at TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            missing INTEGER NOT NULL DEFAULT 0,
            raw_field TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            UNIQUE(station_id, metric, observed_at)
        );
        """
    )
    connection.commit()

    init_db()

    columns = {row["name"] for row in connection.execute("PRAGMA table_info(observation_history)")}
    indexes = {row["name"] for row in connection.execute("PRAGMA index_list(observation_history)")}
    assert {
        "origin",
        "import_run_id",
        "import_source_url",
        "source_station_id",
        "station_mapping_status",
        "station_mapping_version",
        "station_mapping_source_url",
        "station_mapping_retrieved_at",
    } <= columns
    assert "idx_obs_origin" in indexes
    connection.execute(
        """
        INSERT INTO observation_history (
            station_id, station_name, source_key, station_type, metric, value,
            observed_at, retrieved_at, missing, raw_field, origin
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            "synop:12600",
            "Bielsko Biała",
            "synop",
            "synop",
            "temperature",
            10.0,
            "2026-05-01T00:00:00+00:00",
            "2026-07-14T00:00:00+00:00",
            "temperatura",
            "live_refresh",
        ),
    )
    connection.execute(
        """
        INSERT INTO observation_history (
            station_id, station_name, source_key, station_type, metric, value,
            observed_at, retrieved_at, missing, raw_field, origin
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            "synop:12600",
            "BIELSKO-BIAŁA",
            "synop",
            "synop",
            "temperature",
            11.7,
            "2026-05-01T00:00:00+00:00",
            "2026-07-14T00:00:00+00:00",
            "STD/WSTD:blank",
            "archive_import",
        ),
    )
    assert connection.execute(
        """
        SELECT COUNT(*) AS count FROM observation_history
        WHERE station_id = 'synop:12600' AND metric = 'temperature'
            AND observed_at = '2026-05-01T00:00:00+00:00'
        """
    ).fetchone()["count"] == 2


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


def _insert_history_row(
    *,
    station_id: str,
    metric: str,
    value: float,
    observed_at: datetime,
    station_name: str = "Test station",
    station_type: str = "hydro",
) -> None:
    get_engine().execute(
        """
        INSERT INTO observation_history (
            station_id, station_name, source_key, station_type,
            metric, value, unit, observed_at, retrieved_at, missing, raw_field
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            station_id,
            station_name,
            "hydro",
            station_type,
            metric,
            value,
            "cm",
            observed_at.isoformat(),
            datetime(2026, 6, 30, 9, 0, tzinfo=UTC).isoformat(),
            metric,
        ),
    )
    get_engine().commit()


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


def test_query_observations_without_from_returns_newest_limited_rows(
    monkeypatch, tmp_path
) -> None:
    _prepare(tmp_path, monkeypatch)
    repository = ObservationRepository()
    for hour, value in ((6, 1.0), (7, 2.0), (8, 3.0)):
        _insert_history_row(
            station_id="hydro:test",
            metric="water_level",
            value=value,
            observed_at=datetime(2026, 6, 30, hour, tzinfo=UTC),
        )

    records = repository.query_observations(station_id="hydro:test", limit=2)

    assert [record["value"] for record in records] == [2.0, 3.0]


def test_aggregated_observations_keep_metrics_in_separate_buckets(
    monkeypatch, tmp_path
) -> None:
    _prepare(tmp_path, monkeypatch)
    repository = ObservationRepository()
    for minute, water_level, flow in ((1, 10.0, 100.0), (5, 14.0, 110.0)):
        observed_at = datetime(2026, 6, 30, 7, minute, tzinfo=UTC)
        _insert_history_row(
            station_id="hydro:test",
            metric="water_level",
            value=water_level,
            observed_at=observed_at,
        )
        _insert_history_row(
            station_id="hydro:test",
            metric="flow",
            value=flow,
            observed_at=observed_at,
        )

    records = repository.query_observations(
        station_id="hydro:test",
        interval="1h",
    )

    values_by_metric = {record["metric"]: record["value"] for record in records}
    assert values_by_metric == {"flow": 105.0, "water_level": 12.0}


def test_rankings_precipitation_alias_matches_persisted_metric_keys(
    monkeypatch, tmp_path
) -> None:
    _prepare(tmp_path, monkeypatch)
    repository = ObservationRepository()
    _insert_history_row(
        station_id="meteo:a",
        station_name="A",
        station_type="meteo",
        metric="precipitation_sum",
        value=5.0,
        observed_at=datetime(2026, 6, 30, 7, tzinfo=UTC),
    )
    _insert_history_row(
        station_id="meteo:b",
        station_name="B",
        station_type="meteo",
        metric="precipitation_10min",
        value=7.0,
        observed_at=datetime(2026, 6, 30, 7, tzinfo=UTC),
    )

    records = repository.rankings(metric="precipitation", direction="highest")

    assert [record["station_id"] for record in records] == ["meteo:b", "meteo:a"]


def test_rankings_pick_best_value_in_range_not_newest_sample(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    repository = ObservationRepository()
    _insert_history_row(
        station_id="hydro:peak",
        station_name="Peak",
        metric="water_level",
        value=100.0,
        observed_at=datetime(2026, 6, 30, 6, tzinfo=UTC),
    )
    _insert_history_row(
        station_id="hydro:peak",
        station_name="Peak",
        metric="water_level",
        value=40.0,
        observed_at=datetime(2026, 6, 30, 8, tzinfo=UTC),
    )
    _insert_history_row(
        station_id="hydro:steady",
        station_name="Steady",
        metric="water_level",
        value=60.0,
        observed_at=datetime(2026, 6, 30, 8, tzinfo=UTC),
    )

    records = repository.rankings(metric="water_level", direction="highest")

    assert [record["station_id"] for record in records] == ["hydro:peak", "hydro:steady"]
    assert records[0]["value"] == 100.0


def test_rankings_temperature_alias_matches_meteo_metric_keys(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    repository = ObservationRepository()
    _insert_history_row(
        station_id="meteo:a",
        station_name="A",
        station_type="meteo",
        metric="air_temperature",
        value=21.0,
        observed_at=datetime(2026, 6, 30, 7, tzinfo=UTC),
    )
    _insert_history_row(
        station_id="synop:b",
        station_name="B",
        station_type="synop",
        metric="temperature",
        value=15.0,
        observed_at=datetime(2026, 6, 30, 7, tzinfo=UTC),
    )

    records = repository.rankings(metric="temperature", direction="highest")

    assert [record["station_id"] for record in records] == ["meteo:a", "synop:b"]


def test_query_observations_naive_from_is_treated_as_imgw_local_time(
    monkeypatch, tmp_path
) -> None:
    _prepare(tmp_path, monkeypatch)
    repository = ObservationRepository()
    # 05:00Z is the UTC instant for 07:00 Europe/Warsaw (summer, UTC+2).
    _insert_history_row(
        station_id="hydro:test",
        metric="water_level",
        value=9.0,
        observed_at=datetime(2026, 6, 30, 5, 0, tzinfo=UTC),
    )

    records = repository.query_observations(
        station_id="hydro:test",
        observed_from=datetime(2026, 6, 30, 7, 0),
    )

    assert [record["value"] for record in records] == [9.0]


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
