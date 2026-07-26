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
    HydroDailyArchiveBackfiller,
    SynopDailyArchiveBackfiller,
    fetch_bounded_archive,
    get_archive_run,
    parse_hydro_daily_zip,
    parse_synop_daily_zip,
    validate_archive_zip,
)
from app.main import app
from app.operations.archive_history import cleanup_archive_history
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


def _hydro_zip(
    lines: list[str],
    *,
    encoding: str = "cp1250",
    entry_name: str = "codz_2024.csv",
) -> bytes:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr(entry_name, ("\r\n".join(lines) + "\r\n").encode(encoding))
    return zip_buffer.getvalue()


def _hydro_line(
    *,
    station: str = "149180020",
    station_name: str = "CHAŁUPKI",
    hydrological_year: str = "2024",
    hydrological_month: str = "01",
    day: str = "01",
    water_level: str = "113",
    flow: str = "25.400",
    water_temperature: str = "8.1",
    calendar_month: str = "11",
) -> str:
    return ",".join(
        [
            station,
            station_name,
            "Odra (1)",
            hydrological_year,
            hydrological_month,
            day,
            water_level,
            flow,
            water_temperature,
            calendar_month,
        ]
    )


def _hydro_transport(zip_bytes: bytes) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/2024/"):
            return httpx.Response(
                200,
                text='<a href="codz_2024.zip">codz_2024.zip</a>',
            )
        if request.url.path.endswith("/codz_2024.zip"):
            return httpx.Response(
                200,
                content=zip_bytes,
                headers={"Last-Modified": "Thu, 28 Aug 2025 12:27:00 GMT"},
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.mark.parametrize(
    ("line", "encoding", "expected_day"),
    [
        (
            '" 149180020","CHAŁUPKI","Odra (1)","2024","01","01",113,25.400,8.1,"11"',
            "cp1250",
            date(2023, 11, 1),
        ),
        (
            "\ufeff149180020;CHAŁUPKI;Odra (1);2024;03;01;113;25.400;8.1;01",
            "utf-8",
            date(2024, 1, 1),
        ),
        (
            '"149180020,CHAŁUPKI,Odra (1),""2024"",""03"",""02"",113,25.400,8.1,""01"""',
            "cp1250",
            date(2024, 1, 2),
        ),
    ],
)
def test_hydro_daily_parser_supports_reviewed_source_variants(
    line: str,
    encoding: str,
    expected_day: date,
) -> None:
    rows, warnings, duplicates = parse_hydro_daily_zip(
        _hydro_zip([line], encoding=encoding),
        source_url="https://example.test/codz_2024.zip",
        import_run_id="hydro-run",
        imported_at=datetime(2026, 7, 24, tzinfo=UTC),
        observed_from=expected_day,
        observed_to=expected_day,
        source_file_sha256="a" * 64,
        source_file_last_modified="Thu, 28 Aug 2025 12:27:00 GMT",
    )

    assert warnings == []
    assert duplicates == 0
    assert len(rows) == 3
    assert {row["station_id"] for row in rows} == {"hydro:149180020"}
    assert {row["observed_at"].date() for row in rows} == {expected_day}
    assert {row["metric"] for row in rows} == {
        "water_level",
        "flow",
        "water_temperature",
    }
    assert {row["temporal_resolution"] for row in rows} == {"1d"}
    assert {row["quality_status"] for row in rows} == {
        "not_provided_by_source"
    }


def test_hydro_daily_parser_preserves_null_and_sentinel_reasons() -> None:
    line = _hydro_line(
        water_level="9999",
        flow="NULL",
        water_temperature="99.9",
    )
    rows, _warnings, _duplicates = parse_hydro_daily_zip(
        _hydro_zip([line]),
        source_url="https://example.test/codz_2024.zip",
        import_run_id="hydro-missing",
        imported_at=datetime(2026, 7, 24, tzinfo=UTC),
        observed_from=date(2023, 11, 1),
        observed_to=date(2023, 11, 1),
        source_file_sha256="b" * 64,
        source_file_last_modified=None,
    )

    by_metric = {row["metric"]: row for row in rows}
    assert by_metric["water_level"]["missing_reason"] == "source_sentinel"
    assert by_metric["flow"]["missing_reason"] == "source_null"
    assert by_metric["water_temperature"]["missing_reason"] == "source_sentinel"
    assert {row["value"] for row in rows} == {None}
    assert {row["quality_status"] for row in rows} == {None}


def test_hydro_daily_parser_collapses_identical_and_rejects_conflicting_duplicates() -> None:
    line = _hydro_line()
    rows, warnings, duplicates = parse_hydro_daily_zip(
        _hydro_zip([line, line]),
        source_url="https://example.test/codz_2024.zip",
        import_run_id="hydro-duplicates",
        imported_at=datetime(2026, 7, 24, tzinfo=UTC),
        observed_from=date(2023, 11, 1),
        observed_to=date(2023, 11, 1),
        source_file_sha256="c" * 64,
        source_file_last_modified=None,
    )
    assert len(rows) == 3
    assert duplicates == 1
    assert "collapsed 1" in warnings[0]

    with pytest.raises(ArchiveBackfillError) as exc_info:
        parse_hydro_daily_zip(
            _hydro_zip([line, _hydro_line(flow="26.100")]),
            source_url="https://example.test/codz_2024.zip",
            import_run_id="hydro-conflict",
            imported_at=datetime(2026, 7, 24, tzinfo=UTC),
            observed_from=date(2023, 11, 1),
            observed_to=date(2023, 11, 1),
            source_file_sha256="d" * 64,
            source_file_last_modified=None,
        )
    assert exc_info.value.code == "archive_conflicting_duplicate"


def test_hydro_daily_parser_rejects_archive_year_mismatch() -> None:
    with pytest.raises(ArchiveBackfillError) as exc_info:
        parse_hydro_daily_zip(
            _hydro_zip([_hydro_line()]),
            source_url="https://example.test/codz_2024.zip",
            import_run_id="run-1",
            imported_at=datetime(2026, 7, 24, tzinfo=UTC),
            observed_from=date(2023, 11, 1),
            observed_to=date(2023, 11, 1),
            source_file_sha256="abc",
            source_file_last_modified=None,
            expected_hydrological_year=2025,
        )

    assert exc_info.value.code == "archive_row_invalid"


def test_hydro_daily_parser_rejects_bad_columns_dates_and_encoding() -> None:
    common = {
        "source_url": "https://example.test/codz_2024.zip",
        "import_run_id": "run-invalid",
        "imported_at": datetime(2026, 7, 24, tzinfo=UTC),
        "observed_from": date(2023, 11, 1),
        "observed_to": date(2023, 11, 1),
        "source_file_sha256": "abc",
        "source_file_last_modified": None,
    }
    with pytest.raises(ArchiveBackfillError) as columns:
        parse_hydro_daily_zip(_hydro_zip(["only,two"]), **common)
    with pytest.raises(ArchiveBackfillError) as calendar:
        parse_hydro_daily_zip(
            _hydro_zip([_hydro_line(calendar_month="12")]),
            **common,
        )

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("codz_2024.csv", b"\x81")
    with pytest.raises(ArchiveBackfillError) as encoding:
        parse_hydro_daily_zip(zip_buffer.getvalue(), **common)

    assert columns.value.code == "archive_row_invalid"
    assert calendar.value.code == "archive_row_invalid"
    assert encoding.value.code == "archive_encoding_invalid"


def test_hydro_daily_parser_never_merges_codes_by_station_name() -> None:
    rows, _warnings, _duplicates = parse_hydro_daily_zip(
        _hydro_zip(
            [
                _hydro_line(station="149180020", station_name="TA SAMA"),
                _hydro_line(station="149180010", station_name="TA SAMA"),
            ]
        ),
        source_url="https://example.test/codz_2024.zip",
        import_run_id="run-identities",
        imported_at=datetime(2026, 7, 24, tzinfo=UTC),
        observed_from=date(2023, 11, 1),
        observed_to=date(2023, 11, 1),
        source_file_sha256="abc",
        source_file_last_modified=None,
    )

    assert {row["station_id"] for row in rows} == {
        "hydro:149180010",
        "hydro:149180020",
    }
    assert {row["station_name"] for row in rows} == {"TA SAMA"}


def test_hydro_daily_backfill_discovers_monthly_hydrological_file(
    monkeypatch,
    tmp_path,
) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    zip_bytes = _hydro_zip([_hydro_line()])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/2024/"):
            return httpx.Response(
                200,
                text='<a href="codz_2024_01.zip">codz_2024_01.zip</a>',
            )
        if request.url.path.endswith("/codz_2024_01.zip"):
            return httpx.Response(200, content=zip_bytes)
        return httpx.Response(404)

    result = HydroDailyArchiveBackfiller(
        settings,
        transport=httpx.MockTransport(handler),
    ).run(observed_from=date(2023, 11, 1), observed_to=date(2023, 11, 1))

    detail = get_archive_run(result.id)
    assert result.files_total == 1
    assert detail is not None
    assert detail["files"][0]["file_name"] == "codz_2024_01.zip"
    assert detail["files"][0]["hydrological_year"] == 2024


def test_hydro_daily_backfill_updates_and_withdraws_authoritative_rows(
    monkeypatch,
    tmp_path,
) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    first = HydroDailyArchiveBackfiller(
        settings,
        transport=_hydro_transport(
            _hydro_zip(
                [
                    _hydro_line(),
                    _hydro_line(station="149180010", station_name="KRZYŻANOWICE"),
                ]
            )
        ),
    ).run(observed_from=date(2023, 11, 1), observed_to=date(2023, 11, 1))
    second = HydroDailyArchiveBackfiller(
        settings,
        transport=_hydro_transport(_hydro_zip([_hydro_line(flow="30.500")])),
    ).run(observed_from=date(2023, 11, 1), observed_to=date(2023, 11, 1))

    assert first.observations_inserted == 6
    assert second.observations_updated == 3
    assert second.observations_deleted == 3
    remaining = ObservationRepository().query_observations(
        station_id="hydro:149180020"
    )
    assert len(remaining) == 3
    assert next(row for row in remaining if row["metric"] == "flow")["value"] == 30.5
    assert ObservationRepository().query_observations(
        station_id="hydro:149180010"
    ) == []
    run = get_archive_run(second.id)
    assert run is not None
    assert run["observations_deleted"] == 3
    assert run["files"][0]["source_file_sha256"]


def test_hydro_daily_failed_reparse_keeps_previous_atomic_file_slice(
    monkeypatch,
    tmp_path,
) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    HydroDailyArchiveBackfiller(
        settings,
        transport=_hydro_transport(_hydro_zip([_hydro_line()])),
    ).run(observed_from=date(2023, 11, 1), observed_to=date(2023, 11, 1))

    with pytest.raises(ArchiveBackfillError):
        HydroDailyArchiveBackfiller(
            settings,
            transport=_hydro_transport(
                _hydro_zip([_hydro_line(), _hydro_line(flow="99.000")])
            ),
        ).run(observed_from=date(2023, 11, 1), observed_to=date(2023, 11, 1))

    rows = ObservationRepository().query_observations(
        station_id="hydro:149180020"
    )
    assert len(rows) == 3
    assert next(row for row in rows if row["metric"] == "flow")["value"] == 25.4


def test_hydro_daily_same_range_rerun_does_not_duplicate_rows(
    monkeypatch,
    tmp_path,
) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    backfiller = HydroDailyArchiveBackfiller(
        settings,
        transport=_hydro_transport(_hydro_zip([_hydro_line()])),
    )
    first = backfiller.run(
        observed_from=date(2023, 11, 1),
        observed_to=date(2023, 11, 1),
    )
    second = backfiller.run(
        observed_from=date(2023, 11, 1),
        observed_to=date(2023, 11, 1),
    )

    assert first.observations_inserted == 3
    assert second.observations_inserted == 0
    assert len(
        ObservationRepository().query_observations(
            station_id="hydro:149180020"
        )
    ) == 3


def test_hydro_archive_cleanup_is_dry_run_by_default(monkeypatch, tmp_path) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    HydroDailyArchiveBackfiller(
        settings,
        transport=_hydro_transport(_hydro_zip([_hydro_line()])),
    ).run(observed_from=date(2023, 11, 1), observed_to=date(2023, 11, 1))

    dry_run = cleanup_archive_history(
        archive_kind="hydro_daily",
        observed_from=date(2023, 11, 1),
        observed_to=date(2023, 11, 1),
    )
    assert dry_run["matching_observations"] == 3
    assert len(
        ObservationRepository().query_observations(station_id="hydro:149180020")
    ) == 3

    confirmed = cleanup_archive_history(
        archive_kind="hydro_daily",
        observed_from=date(2023, 11, 1),
        observed_to=date(2023, 11, 1),
        confirm=True,
    )
    assert confirmed["deleted"] == 3
    assert ObservationRepository().query_observations(
        station_id="hydro:149180020"
    ) == []


def test_hydro_archive_progress_api_and_archive_only_comparison(
    monkeypatch,
    tmp_path,
) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    result = HydroDailyArchiveBackfiller(
        settings,
        transport=_hydro_transport(_hydro_zip([_hydro_line()])),
    ).run(observed_from=date(2023, 11, 1), observed_to=date(2023, 11, 1))
    apply_test_settings(
        monkeypatch,
        settings.model_copy(update={"admin_token": "test-admin-token"}),
    )
    client = TestClient(app)
    headers = {"X-MeteoLens-Admin-Token": "test-admin-token"}

    denied = client.get("/api/v1/archive/backfill/runs")
    runs = client.get(
        "/api/v1/archive/backfill/runs"
        "?source_key=hydro&archive_kind=hydro_daily&status=completed",
        headers=headers,
    )
    detail = client.get(
        f"/api/v1/archive/backfill/runs/{result.id}",
        headers=headers,
    )
    comparison = client.get(
        "/api/v1/stations/compare"
        "?station_ids=hydro%3A149180020&metric=water_level"
    )
    ranking = client.get(
        "/api/v1/rankings?metric=water_level&type=hydro&direction=highest"
    )
    export_json = client.get(
        "/api/v1/export/station/hydro:149180020/observations.json"
        "?metric=water_level"
    )

    assert denied.status_code == 401
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["archive_kind"] == "hydro_daily"
    assert detail.status_code == 200
    assert detail.json()["files"][0]["status"] == "completed"
    assert comparison.status_code == 200
    assert len(comparison.json()["series"]["hydro:149180020"]) == 1
    assert ranking.status_code == 200
    assert ranking.json()["rankings"][0]["station_id"] == "hydro:149180020"
    assert ranking.json()["rankings"][0]["origin"] == "archive_import"
    assert ranking.json()["rankings"][0]["quality_status"] == (
        "not_provided_by_source"
    )
    exported = export_json.json()["observations"][0]
    assert exported["archive_kind"] == "hydro_daily"
    assert exported["temporal_resolution"] == "1d"
    assert exported["source_file_sha256"]


def test_hydro_observation_api_reports_true_mixed_origin(monkeypatch, tmp_path) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    HydroDailyArchiveBackfiller(
        settings,
        transport=_hydro_transport(_hydro_zip([_hydro_line()])),
    ).run(observed_from=date(2023, 11, 1), observed_to=date(2023, 11, 1))
    get_engine().execute(
        """
        INSERT INTO observation_history (
            station_id, station_name, source_key, station_type, metric, value,
            unit, observed_at, retrieved_at, missing, raw_field, origin
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'live_refresh')
        """,
        (
            "hydro:149180020",
            "NOWA NAZWA",
            "hydro",
            "hydro",
            "water_level",
            114.0,
            "cm",
            datetime(2023, 11, 1, tzinfo=UTC).isoformat(),
            datetime(2023, 11, 1, 8, tzinfo=UTC).isoformat(),
            "stan_wody",
        ),
    )
    get_engine().commit()

    response = TestClient(app).get(
        "/api/v1/stations/hydro:149180020/observations?metric=water_level"
    )

    assert response.status_code == 200
    assert response.json()["series_origin"] == "mixed"
    assert response.json()["origin_counts"] == {
        "archive_import": 1,
        "live_refresh": 1,
    }


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


def test_archive_rows_survive_live_retention_pruning(monkeypatch, tmp_path) -> None:
    settings = _prepare(tmp_path, monkeypatch)
    backfiller = SynopDailyArchiveBackfiller(
        settings,
        transport=_transport(_synop_zip([_row("01")])),
    )
    backfiller.run(observed_from=date(2026, 5, 1), observed_to=date(2026, 5, 1))

    deleted = ObservationRepository().prune_older_than(retention_days=1)

    assert deleted == 0


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


def test_validate_archive_zip_rejects_many_empty_entries_before_opening(tmp_path) -> None:
    settings = _settings(tmp_path).model_copy(update={"archive_zip_max_entries": 5})
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        for index in range(20):
            archive.writestr(f"empty_{index}.txt", "")
    with pytest.raises(ArchiveBackfillError, match="too many entries") as exc_info:
        validate_archive_zip(zip_buffer.getvalue(), settings)
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
