import csv
import zipfile
from datetime import UTC, date, datetime
from io import BytesIO, StringIO
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.engine import get_engine, init_db, reset_engine_cache
from app.db.repository import ObservationRepository
from app.imgw.archive import (
    SYNOP_DAILY_COLUMNS,
    ArchiveBackfillError,
    SynopDailyArchiveBackfiller,
    fetch_bounded_archive,
    parse_synop_daily_zip,
    validate_archive_zip,
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


def _failing_directory_transport() -> httpx.MockTransport:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="missing")

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
    assert by_metric["temperature"]["station_id"] == "synop:12600"
    assert by_metric["temperature"]["source_station_id"] == "349190600"
    assert by_metric["temperature"]["station_mapping_status"] == "mapped"
    assert by_metric["temperature"]["station_mapping_version"] == "2026-07-14"


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
    rows = ObservationRepository().query_observations(station_id="synop:12600")
    assert len(rows) == 20
    assert {row["source_station_id"] for row in rows} == {"349190600"}
    assert {row["station_mapping_status"] for row in rows} == {"mapped"}


def test_synop_daily_backfill_applies_time_range_filter(monkeypatch, tmp_path) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    backfiller = SynopDailyArchiveBackfiller(
        settings,
        transport=_transport(_synop_zip([_row("01"), _row("02")])),
    )

    result = backfiller.run(observed_from=date(2026, 5, 2), observed_to=date(2026, 5, 2))
    records = ObservationRepository().query_observations(
        station_id="synop:12600",
        metric="temperature",
        observed_from=datetime(2026, 5, 1, tzinfo=UTC),
        observed_to=datetime(2026, 5, 3, tzinfo=UTC),
    )

    assert result.rows_seen == 1
    assert [record["observed_at"] for record in records] == [
        "2026-05-02T00:00:00+00:00"
    ]


def test_synop_daily_backfill_records_failed_discovery(monkeypatch, tmp_path) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    backfiller = SynopDailyArchiveBackfiller(
        settings,
        transport=_failing_directory_transport(),
    )

    with pytest.raises(ArchiveBackfillError):
        backfiller.run(observed_from=date(2026, 5, 1), observed_to=date(2026, 5, 1))

    row = get_engine().execute("SELECT * FROM archive_import_runs").fetchone()
    assert row["status"] == "failed"
    assert row["files_total"] == 0
    assert "404" in row["errors"]


def test_archive_rows_follow_retention_pruning(monkeypatch, tmp_path) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    backfiller = SynopDailyArchiveBackfiller(
        settings,
        transport=_transport(_synop_zip([_row("01")])),
    )
    backfiller.run(observed_from=date(2026, 5, 1), observed_to=date(2026, 5, 1))

    deleted = ObservationRepository().prune_older_than(retention_days=1)

    assert deleted == 10


def test_synop_daily_archive_keeps_unmapped_nsp_explicit() -> None:
    rows, warnings = parse_synop_daily_zip(
        _synop_zip([_row("01", station="999999999")]),
        source_url="https://example.test/2026_05_s.zip",
        import_run_id="run-unmapped",
        imported_at=datetime(2026, 7, 14, tzinfo=UTC),
        observed_from=date(2026, 5, 1),
        observed_to=date(2026, 5, 1),
    )

    assert len(warnings) == 1
    assert "unmapped_not_in_mapping_source" in warnings[0]
    assert {row["station_id"] for row in rows} == {"synop-archive:999999999"}
    assert {row["source_station_id"] for row in rows} == {"999999999"}
    assert {row["station_mapping_status"] for row in rows} == {
        "unmapped_not_in_mapping_source"
    }


def test_backfill_reconciles_legacy_archive_rows_through_reviewed_map(
    monkeypatch, tmp_path
) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    get_engine().execute(
        """
        INSERT INTO observation_history (
            station_id, station_name, source_key, station_type, metric, value,
            unit, observed_at, retrieved_at, missing, raw_field, origin,
            import_run_id, import_source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'archive_import', ?, ?)
        """,
        (
            "synop:349190600",
            "BIELSKO-BIAŁA",
            "synop",
            "synop",
            "temperature",
            11.7,
            "°C",
            datetime(2026, 5, 1, tzinfo=UTC).isoformat(),
            datetime(2026, 7, 14, tzinfo=UTC).isoformat(),
            "STD/WSTD:blank",
            "legacy-run",
            "https://example.test/legacy.zip",
        ),
    )
    get_engine().commit()
    backfiller = SynopDailyArchiveBackfiller(
        settings,
        transport=_transport(_synop_zip([_row("02")])),
    )

    backfiller.run(observed_from=date(2026, 5, 2), observed_to=date(2026, 5, 2))

    legacy = ObservationRepository().query_observations(
        station_id="synop:349190600"
    )
    mapped = ObservationRepository().query_observations(
        station_id="synop:12600", metric="temperature"
    )
    assert legacy == []
    assert [row["source_station_id"] for row in mapped] == [
        "349190600",
        "349190600",
    ]
    assert {row["station_mapping_status"] for row in mapped} == {"mapped"}


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
            "synop:12600",
            "BIELSKO-BIAŁA",
            "synop",
            "synop",
            "temperature",
            17.5,
            "°C",
            datetime(2026, 5, 1, tzinfo=UTC).isoformat(),
            datetime(2026, 5, 1, 8, tzinfo=UTC).isoformat(),
            "temperatura",
        ),
    )
    get_engine().commit()

    response = TestClient(app).get(
        "/api/v1/stations/synop:12600/observations?metric=temperature"
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
    archive_point = next(
        point for point in payload["observations"] if point["origin"] == "archive_import"
    )
    assert archive_point["source_station_id"] == "349190600"
    assert archive_point["station_mapping_status"] == "mapped"


def _large_zip(*, entry_count: int = 1, payload_size: int = 0) -> bytes:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        for index in range(entry_count):
            payload = b"A" * payload_size if payload_size else b""
            archive.writestr(f"entry_{index}.csv", payload)
    return zip_buffer.getvalue()


def _many_row_zip(row_count: int) -> bytes:
    text_buffer = StringIO()
    writer = csv.writer(text_buffer)
    for day in range(1, row_count + 1):
        row = _row(f"{day:02d}")
        writer.writerow([row.get(column, "") for column in SYNOP_DAILY_COLUMNS])
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("s_d_05_2026.csv", text_buffer.getvalue().encode("cp1250"))
    return zip_buffer.getvalue()


def test_fetch_bounded_archive_rejects_declared_content_length() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"ignored", headers={"Content-Length": "2048"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ArchiveBackfillError, match="Content-Length") as exc_info:
        fetch_bounded_archive(client, "https://example.test/archive.zip", max_bytes=1024)
    assert exc_info.value.code == "archive_download_too_large"


def test_fetch_bounded_archive_rejects_stream_without_content_length() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        response = httpx.Response(200, content=b"x" * 2048)
        response.headers.pop("content-length", None)
        return response

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ArchiveBackfillError, match="byte limit") as exc_info:
        fetch_bounded_archive(client, "https://example.test/archive.zip", max_bytes=1024)
    assert exc_info.value.code == "archive_download_too_large"


def test_validate_archive_zip_rejects_too_many_entries(tmp_path) -> None:
    settings = _settings(tmp_path).model_copy(update={"archive_zip_max_entries": 2})
    with pytest.raises(ArchiveBackfillError, match="too many entries") as exc_info:
        validate_archive_zip(_large_zip(entry_count=3), settings)
    assert exc_info.value.code == "archive_zip_too_many_entries"


def test_validate_archive_zip_rejects_oversized_entry(tmp_path) -> None:
    settings = _settings(tmp_path).model_copy(update={"archive_zip_entry_max_mb": 1})
    with pytest.raises(ArchiveBackfillError, match="declares") as exc_info:
        validate_archive_zip(_large_zip(payload_size=2 * 1024 * 1024), settings)
    assert exc_info.value.code == "archive_zip_entry_too_large"


def test_validate_archive_zip_rejects_total_uncompressed_size(tmp_path) -> None:
    settings = _settings(tmp_path).model_copy(
        update={
            "archive_zip_entry_max_mb": 10,
            "archive_zip_total_uncompressed_max_mb": 1,
        }
    )
    payload = 768 * 1024
    zip_bytes = _large_zip(entry_count=2, payload_size=payload)
    with pytest.raises(ArchiveBackfillError, match="total uncompressed") as exc_info:
        validate_archive_zip(zip_bytes, settings)
    assert exc_info.value.code == "archive_zip_uncompressed_too_large"


def test_parse_synop_daily_zip_rejects_row_limit(tmp_path) -> None:
    settings = _settings(tmp_path).model_copy(update={"archive_max_rows_per_file": 1})
    with pytest.raises(ArchiveBackfillError, match="row count exceeds") as exc_info:
        parse_synop_daily_zip(
            _many_row_zip(2),
            source_url="https://example.test/2026_05_s.zip",
            import_run_id="run-rows",
            imported_at=datetime(2026, 7, 5, tzinfo=UTC),
            observed_from=date(2026, 5, 1),
            observed_to=date(2026, 5, 31),
            settings=settings,
        )
    assert exc_info.value.code == "archive_row_limit_exceeded"


def test_backfill_records_failed_download_limit(monkeypatch, tmp_path) -> None:
    settings = _prepare(
        tmp_path,
        monkeypatch,
    ).model_copy(update={"archive_download_max_mb": 1})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/2026/"):
            return httpx.Response(
                200,
                text='<a href="2026_05_s.zip">2026_05_s.zip</a>',
            )
        if request.url.path.endswith("/2026_05_s.zip"):
            return httpx.Response(
                200,
                content=b"x" * (2 * 1024 * 1024),
                headers={"Content-Length": str(2 * 1024 * 1024)},
            )
        return httpx.Response(404)

    backfiller = SynopDailyArchiveBackfiller(
        settings,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ArchiveBackfillError):
        backfiller.run(observed_from=date(2026, 5, 1), observed_to=date(2026, 5, 1))

    row = get_engine().execute("SELECT * FROM archive_import_runs").fetchone()
    assert row["status"] == "failed"
    assert row["files_total"] == 1
    assert row["files_processed"] == 0
    assert "Content-Length" in row["errors"]
