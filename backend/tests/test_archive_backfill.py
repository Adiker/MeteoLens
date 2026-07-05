import csv
import zipfile
from datetime import UTC, date, datetime
from io import BytesIO, StringIO
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.engine import get_engine, init_db, reset_engine_cache
from app.db.repository import ObservationRepository
from app.imgw.archive import (
    SYNOP_DAILY_COLUMNS,
    SynopDailyArchiveBackfiller,
    parse_synop_daily_zip,
)
from app.main import app
from tests.settings_helpers import apply_test_settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        cache_dir=tmp_path / "cache",
        geometry_dir=tmp_path / "geometry",
        database_url=f"sqlite:///{tmp_path / 'history.sqlite3'}",
        imgw_base_url="https://danepubliczne.imgw.pl",
        archive_backfill_rate_limit_seconds=0,
    )


def _prepare(tmp_path: Path, monkeypatch) -> Settings:
    reset_engine_cache()
    settings = _settings(tmp_path)
    apply_test_settings(monkeypatch, settings)
    init_db()
    return settings


def _synop_zip(rows: list[dict[str, str]]) -> bytes:
    text_buffer = StringIO()
    writer = csv.writer(text_buffer)
    for row in rows:
        writer.writerow([row.get(column, "") for column in SYNOP_DAILY_COLUMNS])
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("s_d_05_2026.csv", text_buffer.getvalue().encode("cp1250"))
    return zip_buffer.getvalue()


def _row(day: str, *, station: str = "349190600", tavg: str = "11.7") -> dict[str, str]:
    return {
        "NSP": station,
        "POST": "BIELSKO-BIAŁA",
        "ROK": "2026",
        "MC": "05",
        "DZ": day,
        "TMAX": "18.4",
        "TMIN": "5.3",
        "STD": tavg,
        "TMNG": "2.6",
        "SMDB": "",
        "WSMDB": "9",
        "PKSN": "",
        "WPKSN": "8",
        "USL": "3.0",
        "FF10": "",
        "WFF10": "8",
        "FF15": "",
        "WFF15": "8",
        "BRZA": "",
        "WBRZA": "9",
    }


def _transport(zip_bytes: bytes) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/2026/"):
            return httpx.Response(
                200,
                text='<a href="2026_05_s.zip">2026_05_s.zip</a>',
            )
        if request.url.path.endswith("/2026_05_s.zip"):
            return httpx.Response(200, content=zip_bytes)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_synop_daily_archive_parser_preserves_values_nulls_and_statuses() -> None:
    rows, warnings = parse_synop_daily_zip(
        _synop_zip([_row("01")]),
        source_url="https://example.test/2026_05_s.zip",
        import_run_id="run-1",
        imported_at=datetime(2026, 7, 5, tzinfo=UTC),
        observed_from=date(2026, 5, 1),
        observed_to=date(2026, 5, 1),
    )

    assert warnings == []
    by_metric = {row["metric"]: row for row in rows}
    assert by_metric["temperature"]["value"] == 11.7
    assert by_metric["snow_depth"]["value"] is None
    assert by_metric["snow_depth"]["missing"] is True
    assert by_metric["precipitation_sum"]["value"] is None
    assert by_metric["precipitation_sum"]["missing"] is False
    assert by_metric["precipitation_sum"]["raw_field"] == "SMDB/WSMDB:9"


def test_synop_daily_backfill_is_resumable_and_counts_duplicates(monkeypatch, tmp_path) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    backfiller = SynopDailyArchiveBackfiller(
        settings,
        transport=_transport(_synop_zip([_row("01"), _row("02")])),
    )

    first = backfiller.run(observed_from=date(2026, 5, 1), observed_to=date(2026, 5, 2))
    second = backfiller.run(observed_from=date(2026, 5, 1), observed_to=date(2026, 5, 2))

    assert first.observations_inserted == 20
    assert second.observations_inserted == 0
    assert second.observations_updated == 20
    rows = ObservationRepository().query_observations(station_id="synop:349190600")
    assert len(rows) == 20


def test_synop_daily_backfill_applies_time_range_filter(monkeypatch, tmp_path) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    backfiller = SynopDailyArchiveBackfiller(
        settings,
        transport=_transport(_synop_zip([_row("01"), _row("02")])),
    )

    result = backfiller.run(observed_from=date(2026, 5, 2), observed_to=date(2026, 5, 2))
    records = ObservationRepository().query_observations(
        station_id="synop:349190600",
        metric="temperature",
        observed_from=datetime(2026, 5, 1, tzinfo=UTC),
        observed_to=datetime(2026, 5, 3, tzinfo=UTC),
    )

    assert result.rows_seen == 1
    assert [record["observed_at"] for record in records] == [
        "2026-05-02T00:00:00+00:00"
    ]


def test_archive_rows_follow_retention_pruning(monkeypatch, tmp_path) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    backfiller = SynopDailyArchiveBackfiller(
        settings,
        transport=_transport(_synop_zip([_row("01")])),
    )
    backfiller.run(observed_from=date(2026, 5, 1), observed_to=date(2026, 5, 1))

    deleted = ObservationRepository().prune_older_than(retention_days=1)

    assert deleted == 10


def test_observation_api_labels_mixed_live_and_archive_series(monkeypatch, tmp_path) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    backfiller = SynopDailyArchiveBackfiller(
        settings,
        transport=_transport(_synop_zip([_row("01")])),
    )
    backfiller.run(observed_from=date(2026, 5, 1), observed_to=date(2026, 5, 1))
    get_engine().execute(
        """
        INSERT INTO observation_history (
            station_id, station_name, source_key, station_type,
            metric, value, unit, observed_at, retrieved_at, missing, raw_field
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            "synop:349190600",
            "BIELSKO-BIAŁA",
            "synop",
            "synop",
            "temperature",
            17.5,
            "°C",
            datetime(2026, 5, 2, tzinfo=UTC).isoformat(),
            datetime(2026, 5, 2, 8, tzinfo=UTC).isoformat(),
            "temperatura",
        ),
    )
    get_engine().commit()

    response = TestClient(app).get(
        "/api/v1/stations/synop:349190600/observations?metric=temperature"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["series_kind"] == "history"
    assert payload["series_origin"] == "mixed"
    assert payload["origin_counts"] == {"archive_import": 1, "live_refresh": 1}
    assert {point["origin"] for point in payload["observations"]} == {
        "archive_import",
        "live_refresh",
    }
