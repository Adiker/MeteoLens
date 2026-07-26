"""Bounded IMGW archive backfill importers."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import zipfile
from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from io import BytesIO, StringIO
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import Settings
from app.core.observability import metrics
from app.db.engine import get_engine, init_db
from app.db.repository import ArchiveObservationRow, ObservationRepository, _iso
from app.imgw.station_mapping import SynopStationMapping
from app.normalization.models import ATTRIBUTION, PROCESSED_NOTICE

SYNOP_DAILY_BASE_PATH = (
    "/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/synop"
)
HYDRO_DAILY_BASE_PATH = (
    "/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/dobowe"
)
HYDRO_DAILY_ARCHIVE_KIND = "hydro_daily"

SYNOP_DAILY_COLUMNS = [
    "NSP",
    "POST",
    "ROK",
    "MC",
    "DZ",
    "TMAX",
    "WTMAX",
    "TMIN",
    "WTMIN",
    "STD",
    "WSTD",
    "TMNG",
    "WTMNG",
    "SMDB",
    "WSMDB",
    "ROOP",
    "PKSN",
    "WPKSN",
    "RWSN",
    "WRWSN",
    "USL",
    "WUSL",
    "DESZ",
    "WDESZ",
    "SNEG",
    "WSNEG",
    "DISN",
    "WDISN",
    "GRAD",
    "WGRAD",
    "MGLA",
    "WMGLA",
    "ZMGL",
    "WZMGL",
    "SADZ",
    "WSADZ",
    "GOLO",
    "WGOLO",
    "ZMNI",
    "WZMNI",
    "ZMWS",
    "WZMWS",
    "ZMET",
    "WZMET",
    "FF10",
    "WFF10",
    "FF15",
    "WFF15",
    "BRZA",
    "WBRZA",
    "ROSA",
    "WROSA",
    "SZRO",
    "WSZRO",
    "DZPS",
    "WDZPS",
    "DZBL",
    "WDZBL",
    "SGR",
    "IZD",
    "WIZD",
    "IZG",
    "WIZG",
    "AKTN",
    "WAKTN",
]

SYNOP_DAILY_METRICS = (
    ("TMAX", "WTMAX", "max_temperature", "°C"),
    ("TMIN", "WTMIN", "min_temperature", "°C"),
    ("STD", "WSTD", "temperature", "°C"),
    ("TMNG", "WTMNG", "ground_min_temperature", "°C"),
    ("SMDB", "WSMDB", "precipitation_sum", "mm"),
    ("PKSN", "WPKSN", "snow_depth", "cm"),
    ("USL", "WUSL", "sunshine_duration", "h"),
    ("FF10", "WFF10", "wind_ge_10mps_duration", "h"),
    ("FF15", "WFF15", "wind_gt_15mps_duration", "h"),
    ("BRZA", "WBRZA", "thunderstorm_duration", "h"),
)


class ArchiveBackfillError(RuntimeError):
    def __init__(self, message: str, *, code: str = "archive_backfill_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ArchiveFile:
    name: str
    url: str
    hydrological_year: int | None = None
    observed_from: date | None = None
    observed_to: date | None = None


@dataclass(frozen=True)
class SynopDailyBackfillResult:
    id: str
    source_key: str
    archive_kind: str
    status: str
    started_at: datetime
    finished_at: datetime
    observed_from: date
    observed_to: date
    files_total: int
    files_processed: int
    rows_seen: int
    observations_seen: int
    observations_inserted: int
    observations_updated: int
    observations_unchanged: int
    parser_warnings: list[str]
    errors: list[str]
    observations_deleted: int = 0
    duplicate_rows: int = 0
    attribution: str = ATTRIBUTION
    processed_notice: str = PROCESSED_NOTICE

    def model_dump(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source_key": self.source_key,
            "archive_kind": self.archive_kind,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "observed_from": self.observed_from.isoformat(),
            "observed_to": self.observed_to.isoformat(),
            "files_total": self.files_total,
            "files_processed": self.files_processed,
            "rows_seen": self.rows_seen,
            "observations_seen": self.observations_seen,
            "observations_inserted": self.observations_inserted,
            "observations_updated": self.observations_updated,
            "observations_unchanged": self.observations_unchanged,
            "observations_deleted": self.observations_deleted,
            "duplicate_rows": self.duplicate_rows,
            "parser_warnings": self.parser_warnings,
            "errors": self.errors,
            "attribution": self.attribution,
            "processed_notice": self.processed_notice,
        }


class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.hrefs.append(href)


class SynopDailyArchiveBackfiller:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        station_mapping: SynopStationMapping | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.station_mapping = station_mapping or SynopStationMapping.load()
        self.repository = ObservationRepository()
        self.base_url = str(settings.imgw_base_url).rstrip("/")

    def run(self, *, observed_from: date, observed_to: date) -> SynopDailyBackfillResult:
        if observed_from > observed_to:
            raise ArchiveBackfillError(
                "observed_from must not be later than observed_to.",
                code="invalid_time_range",
            )
        day_count = (observed_to - observed_from).days + 1
        if day_count > self.settings.archive_backfill_max_days:
            raise ArchiveBackfillError(
                (
                    "Requested archive range is too large. "
                    f"Limit is {self.settings.archive_backfill_max_days} days."
                ),
                code="archive_range_too_large",
            )

        legacy_reconciliation = self.repository.reconcile_legacy_archive_station_ids(
            self.station_mapping
        )
        run_id = str(uuid4())
        started_at = datetime.now(UTC)
        started_monotonic = time.perf_counter()
        metrics.archive_import_active.inc()
        files: list[ArchiveFile] = []
        rows_seen = 0
        observations_seen = 0
        inserted = 0
        updated = 0
        unchanged = 0
        parser_warnings: list[str] = []
        if legacy_reconciliation["skipped"]:
            parser_warnings.append(
                "Legacy archive reconciliation left "
                f"{legacy_reconciliation['skipped']} conflicting or invalid row(s) "
                "unchanged; review the database before release."
            )
        errors: list[str] = []
        files_processed = 0

        self._write_run(
            run_id=run_id,
            status="running",
            started_at=started_at,
            finished_at=None,
            observed_from=observed_from,
            observed_to=observed_to,
            files_total=0,
            files_processed=files_processed,
            rows_seen=rows_seen,
            observations_seen=observations_seen,
            observations_inserted=inserted,
            observations_updated=updated,
            observations_unchanged=unchanged,
            parser_warnings=parser_warnings,
            errors=errors,
        )

        try:
            files = self._discover_files(observed_from=observed_from, observed_to=observed_to)
            if len(files) > self.settings.archive_backfill_max_files:
                raise ArchiveBackfillError(
                    (
                        "Archive range resolves to too many files. "
                        f"Limit is {self.settings.archive_backfill_max_files} files."
                    ),
                    code="archive_file_limit_exceeded",
                )
            self._write_run(
                run_id=run_id,
                status="running",
                started_at=started_at,
                finished_at=None,
                observed_from=observed_from,
                observed_to=observed_to,
                files_total=len(files),
                files_processed=files_processed,
                rows_seen=rows_seen,
                observations_seen=observations_seen,
                observations_inserted=inserted,
                observations_updated=updated,
                observations_unchanged=unchanged,
                parser_warnings=parser_warnings,
                errors=errors,
            )
            with httpx.Client(
                timeout=self.settings.imgw_timeout_seconds,
                headers={
                    "Accept": "text/html,application/zip,text/csv,*/*",
                    "User-Agent": "MeteoLens/0.1 (+https://github.com/Adiker/MeteoLens)",
                },
                transport=self.transport,
            ) as client:
                for index, archive_file in enumerate(files):
                    content = fetch_bounded_archive(
                        client,
                        archive_file.url,
                        max_bytes=self.settings.archive_download_max_bytes,
                    )
                    parsed_rows, warnings = parse_synop_daily_zip(
                        content,
                        source_url=archive_file.url,
                        import_run_id=run_id,
                        imported_at=datetime.now(UTC),
                        observed_from=observed_from,
                        observed_to=observed_to,
                        station_mapping=self.station_mapping,
                        settings=self.settings,
                    )
                    parser_warnings.extend(warnings)
                    rows_seen += len(
                        {(row["station_id"], row["observed_at"]) for row in parsed_rows}
                    )
                    observations_seen += len(parsed_rows)
                    summary = self.repository.persist_archive_observations(parsed_rows)
                    inserted += summary["inserted"]
                    updated += summary["updated"]
                    unchanged += summary["unchanged"]
                    files_processed += 1
                    self._write_run(
                        run_id=run_id,
                        status="running",
                        started_at=started_at,
                        finished_at=None,
                        observed_from=observed_from,
                        observed_to=observed_to,
                        files_total=len(files),
                        files_processed=files_processed,
                        rows_seen=rows_seen,
                        observations_seen=observations_seen,
                        observations_inserted=inserted,
                        observations_updated=updated,
                        observations_unchanged=unchanged,
                        parser_warnings=parser_warnings,
                        errors=errors,
                    )
                    if (
                        index < len(files) - 1
                        and self.settings.archive_backfill_rate_limit_seconds > 0
                    ):
                        time.sleep(self.settings.archive_backfill_rate_limit_seconds)
        except Exception as exc:
            errors.append(str(exc))
            finished_at = datetime.now(UTC)
            self._write_run(
                run_id=run_id,
                status="failed",
                started_at=started_at,
                finished_at=finished_at,
                observed_from=observed_from,
                observed_to=observed_to,
                files_total=len(files),
                files_processed=files_processed,
                rows_seen=rows_seen,
                observations_seen=observations_seen,
                observations_inserted=inserted,
                observations_updated=updated,
                observations_unchanged=unchanged,
                parser_warnings=parser_warnings,
                errors=errors,
            )
            if isinstance(exc, ArchiveBackfillError):
                metrics.archive_imports.labels(
                    source_key="synop", archive_kind="synop_daily", status="failed"
                ).inc()
                metrics.archive_import_duration.labels(
                    source_key="synop", archive_kind="synop_daily", status="failed"
                ).observe(time.perf_counter() - started_monotonic)
                metrics.archive_import_active.dec()
                raise
            metrics.archive_imports.labels(
                source_key="synop", archive_kind="synop_daily", status="failed"
            ).inc()
            metrics.archive_import_duration.labels(
                source_key="synop", archive_kind="synop_daily", status="failed"
            ).observe(time.perf_counter() - started_monotonic)
            metrics.archive_import_active.dec()
            raise ArchiveBackfillError(str(exc)) from exc

        finished_at = datetime.now(UTC)
        status = "completed_with_warnings" if parser_warnings else "completed"
        self._write_run(
            run_id=run_id,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            observed_from=observed_from,
            observed_to=observed_to,
            files_total=len(files),
            files_processed=files_processed,
            rows_seen=rows_seen,
            observations_seen=observations_seen,
            observations_inserted=inserted,
            observations_updated=updated,
            observations_unchanged=unchanged,
            parser_warnings=parser_warnings,
            errors=errors,
        )
        metrics.archive_imports.labels(
            source_key="synop", archive_kind="synop_daily", status=status
        ).inc()
        metrics.archive_import_duration.labels(
            source_key="synop", archive_kind="synop_daily", status=status
        ).observe(time.perf_counter() - started_monotonic)
        metrics.archive_import_active.dec()
        return SynopDailyBackfillResult(
            id=run_id,
            source_key="synop",
            archive_kind="synop_daily",
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            observed_from=observed_from,
            observed_to=observed_to,
            files_total=len(files),
            files_processed=files_processed,
            rows_seen=rows_seen,
            observations_seen=observations_seen,
            observations_inserted=inserted,
            observations_updated=updated,
            observations_unchanged=unchanged,
            parser_warnings=parser_warnings,
            errors=errors,
        )

    def _discover_files(self, *, observed_from: date, observed_to: date) -> list[ArchiveFile]:
        years = range(observed_from.year, observed_to.year + 1)
        files: list[ArchiveFile] = []
        with httpx.Client(
            timeout=self.settings.imgw_timeout_seconds,
            headers={"User-Agent": "MeteoLens/0.1 (+https://github.com/Adiker/MeteoLens)"},
            transport=self.transport,
        ) as client:
            for year in years:
                directory_url = f"{self.base_url}{SYNOP_DAILY_BASE_PATH}/{year}/"
                response = client.get(directory_url)
                response.raise_for_status()
                parser = _HrefParser()
                parser.feed(response.text)
                for href in parser.hrefs:
                    if not href.endswith(".zip"):
                        continue
                    if not _synop_file_may_overlap(href, observed_from, observed_to):
                        continue
                    files.append(ArchiveFile(name=href, url=f"{directory_url}{href}"))
        return sorted(files, key=lambda item: item.name)

    def _write_run(
        self,
        *,
        run_id: str,
        status: str,
        started_at: datetime,
        finished_at: datetime | None,
        observed_from: date,
        observed_to: date,
        files_total: int,
        files_processed: int,
        rows_seen: int,
        observations_seen: int,
        observations_inserted: int,
        observations_updated: int,
        observations_unchanged: int,
        parser_warnings: list[str],
        errors: list[str],
    ) -> None:
        init_db()
        connection = get_engine()
        connection.execute(
            """
            INSERT INTO archive_import_runs (
                id, source_key, archive_kind, status, started_at, finished_at,
                observed_from, observed_to, files_total, files_processed,
                rows_seen, observations_seen, observations_inserted,
                observations_updated, observations_unchanged, parser_warnings,
                errors, attribution, processed_notice
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                finished_at = excluded.finished_at,
                files_total = excluded.files_total,
                files_processed = excluded.files_processed,
                rows_seen = excluded.rows_seen,
                observations_seen = excluded.observations_seen,
                observations_inserted = excluded.observations_inserted,
                observations_updated = excluded.observations_updated,
                observations_unchanged = excluded.observations_unchanged,
                parser_warnings = excluded.parser_warnings,
                errors = excluded.errors
            """,
            (
                run_id,
                "synop",
                "synop_daily",
                status,
                _iso(started_at),
                _iso(finished_at) if finished_at else None,
                observed_from.isoformat(),
                observed_to.isoformat(),
                files_total,
                files_processed,
                rows_seen,
                observations_seen,
                observations_inserted,
                observations_updated,
                observations_unchanged,
                json.dumps(parser_warnings, ensure_ascii=False),
                json.dumps(errors, ensure_ascii=False),
                ATTRIBUTION,
                PROCESSED_NOTICE,
            ),
        )
        connection.commit()


class HydroDailyArchiveBackfiller:
    """Import bounded daily hydrological CODZ archives."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.repository = ObservationRepository()
        self.base_url = str(settings.imgw_base_url).rstrip("/")

    def run(self, *, observed_from: date, observed_to: date) -> SynopDailyBackfillResult:
        if observed_from > observed_to:
            raise ArchiveBackfillError(
                "observed_from must not be later than observed_to.",
                code="invalid_time_range",
            )
        day_count = (observed_to - observed_from).days + 1
        if day_count > self.settings.archive_backfill_max_days:
            raise ArchiveBackfillError(
                (
                    "Requested archive range is too large. "
                    f"Limit is {self.settings.archive_backfill_max_days} days."
                ),
                code="archive_range_too_large",
            )

        run_id = str(uuid4())
        started_at = datetime.now(UTC)
        started_monotonic = time.perf_counter()
        metrics.archive_import_active.inc()
        files: list[ArchiveFile] = []
        files_processed = 0
        rows_seen = 0
        observations_seen = 0
        inserted = 0
        updated = 0
        unchanged = 0
        deleted = 0
        duplicate_rows = 0
        parser_warnings: list[str] = []
        errors: list[str] = []
        _write_archive_run(
            run_id=run_id,
            source_key="hydro",
            archive_kind=HYDRO_DAILY_ARCHIVE_KIND,
            status="running",
            started_at=started_at,
            finished_at=None,
            observed_from=observed_from,
            observed_to=observed_to,
            files_total=0,
            files_processed=0,
            rows_seen=0,
            observations_seen=0,
            observations_inserted=0,
            observations_updated=0,
            observations_unchanged=0,
            observations_deleted=0,
            duplicate_rows=0,
            parser_warnings=[],
            errors=[],
        )

        try:
            files, discovery_warnings = self._discover_files(
                observed_from=observed_from,
                observed_to=observed_to,
            )
            parser_warnings.extend(discovery_warnings)
            if not files:
                raise ArchiveBackfillError(
                    "No supported CODZ archive files overlap the requested range.",
                    code="archive_files_not_found",
                )
            if len(files) > self.settings.archive_backfill_max_files:
                raise ArchiveBackfillError(
                    (
                        "Archive range resolves to too many files. "
                        f"Limit is {self.settings.archive_backfill_max_files} files."
                    ),
                    code="archive_file_limit_exceeded",
                )
            _write_archive_run(
                run_id=run_id,
                source_key="hydro",
                archive_kind=HYDRO_DAILY_ARCHIVE_KIND,
                status="running",
                started_at=started_at,
                finished_at=None,
                observed_from=observed_from,
                observed_to=observed_to,
                files_total=len(files),
                files_processed=files_processed,
                rows_seen=rows_seen,
                observations_seen=observations_seen,
                observations_inserted=inserted,
                observations_updated=updated,
                observations_unchanged=unchanged,
                observations_deleted=deleted,
                duplicate_rows=duplicate_rows,
                parser_warnings=parser_warnings,
                errors=errors,
            )
            with httpx.Client(
                timeout=self.settings.imgw_timeout_seconds,
                headers={
                    "Accept": "text/html,application/zip,text/csv,*/*",
                    "User-Agent": "MeteoLens/0.1 (+https://github.com/Adiker/MeteoLens)",
                },
                transport=self.transport,
            ) as client:
                for index, archive_file in enumerate(files):
                    file_started_at = datetime.now(UTC)
                    source_file_sha256: str | None = None
                    source_file_last_modified: str | None = None
                    _write_archive_run_file(
                        run_id=run_id,
                        archive_file=archive_file,
                        status="running",
                        started_at=file_started_at,
                    )
                    try:
                        content, response_metadata = fetch_bounded_archive_with_metadata(
                            client,
                            archive_file.url,
                            max_bytes=self.settings.archive_download_max_bytes,
                        )
                        source_file_sha256 = hashlib.sha256(content).hexdigest()
                        source_file_last_modified = response_metadata.get("last-modified")
                        parsed_rows, warnings, file_duplicate_rows = parse_hydro_daily_zip(
                            content,
                            source_url=archive_file.url,
                            import_run_id=run_id,
                            imported_at=datetime.now(UTC),
                            observed_from=archive_file.observed_from or observed_from,
                            observed_to=archive_file.observed_to or observed_to,
                            source_file_sha256=source_file_sha256,
                            source_file_last_modified=source_file_last_modified,
                            expected_hydrological_year=archive_file.hydrological_year,
                            settings=self.settings,
                        )
                        file_rows_seen = len(
                            {
                                (row["station_id"], row["observed_at"])
                                for row in parsed_rows
                            }
                        )
                        summary = self.repository.sync_archive_observations(
                            parsed_rows,
                            source_key="hydro",
                            archive_kind=HYDRO_DAILY_ARCHIVE_KIND,
                            observed_from=datetime.combine(
                                archive_file.observed_from or observed_from,
                                datetime.min.time(),
                                tzinfo=UTC,
                            ),
                            observed_to=datetime.combine(
                                archive_file.observed_to or observed_to,
                                datetime.min.time(),
                                tzinfo=UTC,
                            ),
                        )
                    except Exception as exc:
                        _write_archive_run_file(
                            run_id=run_id,
                            archive_file=archive_file,
                            status="failed",
                            started_at=file_started_at,
                            finished_at=datetime.now(UTC),
                            source_file_sha256=source_file_sha256,
                            source_file_last_modified=source_file_last_modified,
                            errors=[str(exc)],
                        )
                        raise

                    parser_warnings.extend(warnings)
                    rows_seen += file_rows_seen
                    observations_seen += len(parsed_rows)
                    inserted += summary["inserted"]
                    updated += summary["updated"]
                    unchanged += summary["unchanged"]
                    deleted += summary["deleted"]
                    duplicate_rows += file_duplicate_rows
                    files_processed += 1
                    _write_archive_run_file(
                        run_id=run_id,
                        archive_file=archive_file,
                        status="completed_with_warnings"
                        if warnings or file_duplicate_rows
                        else "completed",
                        started_at=file_started_at,
                        finished_at=datetime.now(UTC),
                        source_file_sha256=source_file_sha256,
                        source_file_last_modified=source_file_last_modified,
                        rows_seen=file_rows_seen,
                        observations_seen=len(parsed_rows),
                        observations_inserted=summary["inserted"],
                        observations_updated=summary["updated"],
                        observations_unchanged=summary["unchanged"],
                        observations_deleted=summary["deleted"],
                        duplicate_rows=file_duplicate_rows,
                        parser_warnings=warnings,
                    )
                    _write_archive_run(
                        run_id=run_id,
                        source_key="hydro",
                        archive_kind=HYDRO_DAILY_ARCHIVE_KIND,
                        status="running",
                        started_at=started_at,
                        finished_at=None,
                        observed_from=observed_from,
                        observed_to=observed_to,
                        files_total=len(files),
                        files_processed=files_processed,
                        rows_seen=rows_seen,
                        observations_seen=observations_seen,
                        observations_inserted=inserted,
                        observations_updated=updated,
                        observations_unchanged=unchanged,
                        observations_deleted=deleted,
                        duplicate_rows=duplicate_rows,
                        parser_warnings=parser_warnings,
                        errors=errors,
                    )
                    if (
                        index < len(files) - 1
                        and self.settings.archive_backfill_rate_limit_seconds > 0
                    ):
                        time.sleep(self.settings.archive_backfill_rate_limit_seconds)
        except Exception as exc:
            errors.append(str(exc))
            finished_at = datetime.now(UTC)
            _write_archive_run(
                run_id=run_id,
                source_key="hydro",
                archive_kind=HYDRO_DAILY_ARCHIVE_KIND,
                status="failed",
                started_at=started_at,
                finished_at=finished_at,
                observed_from=observed_from,
                observed_to=observed_to,
                files_total=len(files),
                files_processed=files_processed,
                rows_seen=rows_seen,
                observations_seen=observations_seen,
                observations_inserted=inserted,
                observations_updated=updated,
                observations_unchanged=unchanged,
                observations_deleted=deleted,
                duplicate_rows=duplicate_rows,
                parser_warnings=parser_warnings,
                errors=errors,
            )
            _record_archive_metrics(
                source_key="hydro",
                archive_kind=HYDRO_DAILY_ARCHIVE_KIND,
                status="failed",
                started_monotonic=started_monotonic,
            )
            if isinstance(exc, ArchiveBackfillError):
                raise
            raise ArchiveBackfillError(str(exc)) from exc

        finished_at = datetime.now(UTC)
        status = (
            "completed_with_warnings"
            if parser_warnings or duplicate_rows
            else "completed"
        )
        _write_archive_run(
            run_id=run_id,
            source_key="hydro",
            archive_kind=HYDRO_DAILY_ARCHIVE_KIND,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            observed_from=observed_from,
            observed_to=observed_to,
            files_total=len(files),
            files_processed=files_processed,
            rows_seen=rows_seen,
            observations_seen=observations_seen,
            observations_inserted=inserted,
            observations_updated=updated,
            observations_unchanged=unchanged,
            observations_deleted=deleted,
            duplicate_rows=duplicate_rows,
            parser_warnings=parser_warnings,
            errors=errors,
        )
        _record_archive_metrics(
            source_key="hydro",
            archive_kind=HYDRO_DAILY_ARCHIVE_KIND,
            status=status,
            started_monotonic=started_monotonic,
        )
        return SynopDailyBackfillResult(
            id=run_id,
            source_key="hydro",
            archive_kind=HYDRO_DAILY_ARCHIVE_KIND,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            observed_from=observed_from,
            observed_to=observed_to,
            files_total=len(files),
            files_processed=files_processed,
            rows_seen=rows_seen,
            observations_seen=observations_seen,
            observations_inserted=inserted,
            observations_updated=updated,
            observations_unchanged=unchanged,
            observations_deleted=deleted,
            duplicate_rows=duplicate_rows,
            parser_warnings=parser_warnings,
            errors=errors,
        )

    def _discover_files(
        self,
        *,
        observed_from: date,
        observed_to: date,
    ) -> tuple[list[ArchiveFile], list[str]]:
        hydrological_years = range(
            _hydrological_year(observed_from),
            _hydrological_year(observed_to) + 1,
        )
        files: list[ArchiveFile] = []
        warnings: list[str] = []
        with httpx.Client(
            timeout=self.settings.imgw_timeout_seconds,
            headers={"User-Agent": "MeteoLens/0.1 (+https://github.com/Adiker/MeteoLens)"},
            transport=self.transport,
        ) as client:
            for hydrological_year in hydrological_years:
                directory_url = (
                    f"{self.base_url}{HYDRO_DAILY_BASE_PATH}/{hydrological_year}/"
                )
                response = client.get(directory_url)
                if response.status_code == 404:
                    warnings.append(
                        f"Hydrological year {hydrological_year} is not published."
                    )
                    continue
                response.raise_for_status()
                parser = _HrefParser()
                parser.feed(response.text)
                supported = sorted(
                    {
                        href
                        for href in parser.hrefs
                        if re.fullmatch(
                            rf"codz_{hydrological_year}(?:_\d{{2}})?\.zip",
                            href,
                            flags=re.IGNORECASE,
                        )
                    }
                )
                annual_name = f"codz_{hydrological_year}.zip"
                if annual_name in supported:
                    if len(supported) > 1:
                        warnings.append(
                            f"{hydrological_year}: annual CODZ file preferred over "
                            "overlapping monthly files."
                        )
                    file_from, file_to = _hydrological_year_bounds(hydrological_year)
                    clipped = _clip_date_range(
                        file_from,
                        file_to,
                        observed_from,
                        observed_to,
                    )
                    if clipped:
                        files.append(
                            ArchiveFile(
                                name=annual_name,
                                url=f"{directory_url}{annual_name}",
                                hydrological_year=hydrological_year,
                                observed_from=clipped[0],
                                observed_to=clipped[1],
                            )
                        )
                    continue
                for name in supported:
                    match = re.fullmatch(
                        rf"codz_{hydrological_year}_(\d{{2}})\.zip",
                        name,
                        flags=re.IGNORECASE,
                    )
                    if match is None:
                        continue
                    file_from, file_to = _hydrological_month_bounds(
                        hydrological_year,
                        int(match.group(1)),
                    )
                    clipped = _clip_date_range(
                        file_from,
                        file_to,
                        observed_from,
                        observed_to,
                    )
                    if clipped:
                        files.append(
                            ArchiveFile(
                                name=name,
                                url=f"{directory_url}{name}",
                                hydrological_year=hydrological_year,
                                observed_from=clipped[0],
                                observed_to=clipped[1],
                            )
                        )
        return sorted(files, key=lambda item: item.url), warnings


def _record_archive_metrics(
    *,
    source_key: str,
    archive_kind: str,
    status: str,
    started_monotonic: float,
) -> None:
    metrics.archive_imports.labels(
        source_key=source_key,
        archive_kind=archive_kind,
        status=status,
    ).inc()
    metrics.archive_import_duration.labels(
        source_key=source_key,
        archive_kind=archive_kind,
        status=status,
    ).observe(time.perf_counter() - started_monotonic)
    metrics.archive_import_active.dec()


def _write_archive_run(
    *,
    run_id: str,
    source_key: str,
    archive_kind: str,
    status: str,
    started_at: datetime,
    finished_at: datetime | None,
    observed_from: date,
    observed_to: date,
    files_total: int,
    files_processed: int,
    rows_seen: int,
    observations_seen: int,
    observations_inserted: int,
    observations_updated: int,
    observations_unchanged: int,
    observations_deleted: int,
    duplicate_rows: int,
    parser_warnings: list[str],
    errors: list[str],
) -> None:
    init_db()
    connection = get_engine()
    connection.execute(
        """
        INSERT INTO archive_import_runs (
            id, source_key, archive_kind, status, started_at, finished_at,
            observed_from, observed_to, files_total, files_processed,
            rows_seen, observations_seen, observations_inserted,
            observations_updated, observations_unchanged, observations_deleted,
            duplicate_rows, parser_warnings, errors, attribution, processed_notice
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            status = excluded.status,
            finished_at = excluded.finished_at,
            files_total = excluded.files_total,
            files_processed = excluded.files_processed,
            rows_seen = excluded.rows_seen,
            observations_seen = excluded.observations_seen,
            observations_inserted = excluded.observations_inserted,
            observations_updated = excluded.observations_updated,
            observations_unchanged = excluded.observations_unchanged,
            observations_deleted = excluded.observations_deleted,
            duplicate_rows = excluded.duplicate_rows,
            parser_warnings = excluded.parser_warnings,
            errors = excluded.errors
        """,
        (
            run_id,
            source_key,
            archive_kind,
            status,
            _iso(started_at),
            _iso(finished_at) if finished_at else None,
            observed_from.isoformat(),
            observed_to.isoformat(),
            files_total,
            files_processed,
            rows_seen,
            observations_seen,
            observations_inserted,
            observations_updated,
            observations_unchanged,
            observations_deleted,
            duplicate_rows,
            json.dumps(parser_warnings, ensure_ascii=False),
            json.dumps(errors, ensure_ascii=False),
            ATTRIBUTION,
            PROCESSED_NOTICE,
        ),
    )
    connection.commit()


def _write_archive_run_file(
    *,
    run_id: str,
    archive_file: ArchiveFile,
    status: str,
    started_at: datetime,
    finished_at: datetime | None = None,
    source_file_sha256: str | None = None,
    source_file_last_modified: str | None = None,
    rows_seen: int = 0,
    observations_seen: int = 0,
    observations_inserted: int = 0,
    observations_updated: int = 0,
    observations_unchanged: int = 0,
    observations_deleted: int = 0,
    duplicate_rows: int = 0,
    parser_warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> None:
    init_db()
    connection = get_engine()
    connection.execute(
        """
        INSERT INTO archive_import_run_files (
            run_id, source_url, file_name, hydrological_year, status,
            started_at, finished_at, source_file_sha256,
            source_file_last_modified, rows_seen, observations_seen,
            observations_inserted, observations_updated,
            observations_unchanged, observations_deleted, duplicate_rows,
            parser_warnings, errors
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, source_url) DO UPDATE SET
            status = excluded.status,
            finished_at = excluded.finished_at,
            source_file_sha256 = excluded.source_file_sha256,
            source_file_last_modified = excluded.source_file_last_modified,
            rows_seen = excluded.rows_seen,
            observations_seen = excluded.observations_seen,
            observations_inserted = excluded.observations_inserted,
            observations_updated = excluded.observations_updated,
            observations_unchanged = excluded.observations_unchanged,
            observations_deleted = excluded.observations_deleted,
            duplicate_rows = excluded.duplicate_rows,
            parser_warnings = excluded.parser_warnings,
            errors = excluded.errors
        """,
        (
            run_id,
            archive_file.url,
            archive_file.name,
            archive_file.hydrological_year,
            status,
            _iso(started_at),
            _iso(finished_at) if finished_at else None,
            source_file_sha256,
            source_file_last_modified,
            rows_seen,
            observations_seen,
            observations_inserted,
            observations_updated,
            observations_unchanged,
            observations_deleted,
            duplicate_rows,
            json.dumps(parser_warnings or [], ensure_ascii=False),
            json.dumps(errors or [], ensure_ascii=False),
        ),
    )
    connection.commit()


def list_archive_runs(
    *,
    source_key: str | None = None,
    archive_kind: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    init_db()
    clauses: list[str] = []
    params: list[Any] = []
    for column, value in (
        ("source_key", source_key),
        ("archive_kind", archive_kind),
        ("status", status),
    ):
        if value is not None:
            clauses.append(f"{column} = ?")
            params.append(value)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = get_engine().execute(
        f"""
        SELECT *
        FROM archive_import_runs
        {where}
        ORDER BY started_at DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [_archive_run_payload(row, include_files=False) for row in rows]


def get_archive_run(run_id: str) -> dict[str, Any] | None:
    init_db()
    connection = get_engine()
    row = connection.execute(
        "SELECT * FROM archive_import_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    payload = _archive_run_payload(row, include_files=False)
    files = connection.execute(
        """
        SELECT *
        FROM archive_import_run_files
        WHERE run_id = ?
        ORDER BY started_at, source_url
        """,
        (run_id,),
    ).fetchall()
    payload["files"] = [_archive_run_file_payload(file_row) for file_row in files]
    return payload


def _archive_run_payload(row: Any, *, include_files: bool) -> dict[str, Any]:
    payload = dict(row)
    payload["parser_warnings"] = json.loads(payload["parser_warnings"])
    payload["errors"] = json.loads(payload["errors"])
    if include_files:
        payload["files"] = []
    return payload


def _archive_run_file_payload(row: Any) -> dict[str, Any]:
    payload = dict(row)
    payload["parser_warnings"] = json.loads(payload["parser_warnings"])
    payload["errors"] = json.loads(payload["errors"])
    return payload


def mark_interrupted_archive_runs() -> int:
    """Close runs left as running after a process or host restart."""
    init_db()
    finished_at = datetime.now(UTC).isoformat()
    connection = get_engine()
    connection.execute(
        """
        UPDATE archive_import_run_files
        SET status = 'interrupted', finished_at = ?,
            errors = CASE
                WHEN errors = '[]' THEN '["process_restarted"]'
                ELSE errors
            END
        WHERE status = 'running'
        """,
        (finished_at,),
    )
    cursor = connection.execute(
        """
        UPDATE archive_import_runs
        SET status = 'interrupted', finished_at = ?,
            errors = CASE
                WHEN errors = '[]' THEN '["process_restarted"]'
                ELSE errors
            END
        WHERE status = 'running'
        """,
        (finished_at,),
    )
    connection.commit()
    return cursor.rowcount


def fetch_bounded_archive(
    client: httpx.Client,
    url: str,
    *,
    max_bytes: int,
) -> bytes:
    """Download an archive file with a hard byte limit."""
    content, _metadata = fetch_bounded_archive_with_metadata(
        client,
        url,
        max_bytes=max_bytes,
    )
    return content


def fetch_bounded_archive_with_metadata(
    client: httpx.Client,
    url: str,
    *,
    max_bytes: int,
) -> tuple[bytes, dict[str, str]]:
    """Download an archive file with a hard byte limit and response provenance."""
    with client.stream("GET", url) as response:
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            else:
                if declared > max_bytes:
                    raise ArchiveBackfillError(
                        (
                            "Archive download Content-Length "
                            f"({declared} bytes) exceeds the configured limit "
                            f"({max_bytes} bytes)."
                        ),
                        code="archive_download_too_large",
                    )
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > max_bytes:
                raise ArchiveBackfillError(
                    (
                        "Archive download exceeded the configured "
                        f"{max_bytes} byte limit."
                    ),
                    code="archive_download_too_large",
                )
            chunks.append(chunk)
        metadata = {
            key: value
            for key in ("etag", "last-modified")
            if (value := response.headers.get(key)) is not None
        }
    return b"".join(chunks), metadata


_EOCD_SIGNATURE = b"PK\x05\x06"
_ZIP64_EOCD_LOCATOR_SIGNATURE = b"PK\x06\x07"
_ZIP64_EOCD_SIGNATURE = b"PK\x06\x06"
_MAX_ZIP_COMMENT_LENGTH = 65_535
_EOCD_MIN_SIZE = 22
_ZIP64_EOCD_LOCATOR_SIZE = 20


def _inspect_zip_central_directory(
    content: bytes,
    *,
    max_entries: int,
    max_central_directory_bytes: int,
) -> tuple[int, int]:
    """Read EOCD metadata before zipfile parses the central directory."""
    if len(content) < _EOCD_MIN_SIZE:
        raise ArchiveBackfillError(
            "Archive ZIP is empty or truncated.",
            code="archive_zip_invalid",
        )
    search_start = max(0, len(content) - (_MAX_ZIP_COMMENT_LENGTH + _EOCD_MIN_SIZE))
    eocd_offset = content.rfind(_EOCD_SIGNATURE, search_start)
    if eocd_offset < 0:
        raise ArchiveBackfillError(
            "Archive ZIP is missing an end-of-central-directory record.",
            code="archive_zip_invalid",
        )
    if eocd_offset + _EOCD_MIN_SIZE > len(content):
        raise ArchiveBackfillError(
            "Archive ZIP end-of-central-directory record is truncated.",
            code="archive_zip_invalid",
        )

    entries_on_disk = int.from_bytes(content[eocd_offset + 8 : eocd_offset + 10], "little")
    total_entries = int.from_bytes(content[eocd_offset + 10 : eocd_offset + 12], "little")
    central_directory_size = int.from_bytes(
        content[eocd_offset + 12 : eocd_offset + 16],
        "little",
    )
    comment_length = int.from_bytes(content[eocd_offset + 20 : eocd_offset + 22], "little")
    expected_end = eocd_offset + _EOCD_MIN_SIZE + comment_length
    if expected_end != len(content):
        raise ArchiveBackfillError(
            "Archive ZIP end-of-central-directory record does not match file size.",
            code="archive_zip_invalid",
        )

    if (
        entries_on_disk == 0xFFFF
        or total_entries == 0xFFFF
        or central_directory_size == 0xFFFF_FFFF
    ):
        total_entries, central_directory_size = _read_zip64_directory_metadata(
            content,
            eocd_offset=eocd_offset,
        )

    if total_entries > max_entries:
        raise ArchiveBackfillError(
            (
                "Archive ZIP contains too many entries "
                f"({total_entries}). Limit is {max_entries}."
            ),
            code="archive_zip_too_many_entries",
        )
    if central_directory_size > max_central_directory_bytes:
        raise ArchiveBackfillError(
            (
                "Archive ZIP central directory is too large "
                f"({central_directory_size} bytes). Limit is "
                f"{max_central_directory_bytes} bytes."
            ),
            code="archive_zip_central_directory_too_large",
        )
    return total_entries, central_directory_size


def _read_zip64_directory_metadata(content: bytes, *, eocd_offset: int) -> tuple[int, int]:
    locator_offset = eocd_offset - _ZIP64_EOCD_LOCATOR_SIZE
    if locator_offset < 0:
        raise ArchiveBackfillError(
            "Archive ZIP declares ZIP64 metadata but the locator is missing.",
            code="archive_zip_invalid",
        )
    if content[locator_offset : locator_offset + 4] != _ZIP64_EOCD_LOCATOR_SIGNATURE:
        raise ArchiveBackfillError(
            "Archive ZIP declares ZIP64 entry counts but the locator is missing.",
            code="archive_zip_invalid",
        )
    zip64_eocd_offset = int.from_bytes(
        content[locator_offset + 8 : locator_offset + 16],
        "little",
    )
    if zip64_eocd_offset < 0 or zip64_eocd_offset + 56 > len(content):
        raise ArchiveBackfillError(
            "Archive ZIP ZIP64 end-of-central-directory record is invalid.",
            code="archive_zip_invalid",
        )
    if content[zip64_eocd_offset : zip64_eocd_offset + 4] != _ZIP64_EOCD_SIGNATURE:
        raise ArchiveBackfillError(
            "Archive ZIP ZIP64 end-of-central-directory record is invalid.",
            code="archive_zip_invalid",
        )
    total_entries = int.from_bytes(
        content[zip64_eocd_offset + 32 : zip64_eocd_offset + 40],
        "little",
    )
    central_directory_size = int.from_bytes(
        content[zip64_eocd_offset + 40 : zip64_eocd_offset + 48],
        "little",
    )
    return total_entries, central_directory_size


def validate_archive_zip(content: bytes, settings: Settings) -> None:
    """Reject ZIP bombs and oversized archives before extraction."""
    max_entries = settings.archive_zip_max_entries
    max_entry_bytes = settings.archive_zip_entry_max_bytes
    max_total_bytes = settings.archive_zip_total_uncompressed_max_bytes
    max_central_directory_bytes = max(max_entries * 1024, 65_536)
    _inspect_zip_central_directory(
        content,
        max_entries=max_entries,
        max_central_directory_bytes=max_central_directory_bytes,
    )
    with zipfile.ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
        if len(entries) > max_entries:
            raise ArchiveBackfillError(
                (
                    "Archive ZIP contains too many entries "
                    f"({len(entries)}). Limit is {max_entries}."
                ),
                code="archive_zip_too_many_entries",
            )
        total_uncompressed = 0
        for info in entries:
            if info.file_size > max_entry_bytes:
                raise ArchiveBackfillError(
                    (
                        f"Archive ZIP entry {info.filename!r} declares "
                        f"{info.file_size} uncompressed bytes; limit is "
                        f"{max_entry_bytes} bytes."
                    ),
                    code="archive_zip_entry_too_large",
                )
            total_uncompressed += info.file_size
            if total_uncompressed > max_total_bytes:
                raise ArchiveBackfillError(
                    (
                        "Archive ZIP declares "
                        f"{total_uncompressed} total uncompressed bytes; "
                        f"limit is {max_total_bytes} bytes."
                    ),
                    code="archive_zip_uncompressed_too_large",
                )


HYDRO_DAILY_COLUMNS = (
    "PSKDSZS",
    "PSNZWP",
    "KDNRZK",
    "COROKH",
    "COMSCH",
    "CODZIEN",
    "COSTAN",
    "COPRZP",
    "COPTMP",
    "COMSCK",
)

HYDRO_DAILY_METRICS = (
    ("COSTAN", "water_level", "cm", Decimal("9999")),
    ("COPRZP", "flow", "m³/s", Decimal("99999.999")),
    ("COPTMP", "water_temperature", "°C", Decimal("99.9")),
)


def parse_hydro_daily_zip(
    content: bytes,
    *,
    source_url: str,
    import_run_id: str,
    imported_at: datetime,
    observed_from: date,
    observed_to: date,
    source_file_sha256: str,
    source_file_last_modified: str | None,
    expected_hydrological_year: int | None = None,
    settings: Settings | None = None,
) -> tuple[list[ArchiveObservationRow], list[str], int]:
    """Parse a reviewed daily CODZ archive slice without guessing source fields."""
    active_settings = settings or Settings()
    validate_archive_zip(content, active_settings)
    max_entry_bytes = active_settings.archive_zip_entry_max_bytes
    max_total_bytes = active_settings.archive_zip_total_uncompressed_max_bytes
    max_rows = active_settings.archive_max_rows_per_file
    records: list[ArchiveObservationRow] = []
    warnings: list[str] = []
    duplicate_rows = 0
    rows_seen = 0
    total_uncompressed = 0
    seen_rows: dict[tuple[str, datetime], tuple[str, ...]] = {}

    with zipfile.ZipFile(BytesIO(content)) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ArchiveBackfillError(
                f"{source_url}: no CSV files found in ZIP.",
                code="archive_zip_missing_csv",
            )
        for name in csv_names:
            raw = archive.read(name)
            total_uncompressed += len(raw)
            if len(raw) > max_entry_bytes:
                raise ArchiveBackfillError(
                    (
                        f"Archive ZIP entry {name!r} expanded to {len(raw)} bytes; "
                        f"limit is {max_entry_bytes} bytes."
                    ),
                    code="archive_zip_entry_too_large",
                )
            if total_uncompressed > max_total_bytes:
                raise ArchiveBackfillError(
                    (
                        f"Archive ZIP expanded to {total_uncompressed} total bytes; "
                        f"limit is {max_total_bytes} bytes."
                    ),
                    code="archive_zip_uncompressed_too_large",
                )
            text = _decode_hydro_archive_text(raw, source_name=name)
            for line_number, line in enumerate(text.splitlines(), start=1):
                if not line.strip():
                    continue
                rows_seen += 1
                if rows_seen > max_rows:
                    raise ArchiveBackfillError(
                        (
                            "Archive CSV row count exceeds the configured limit "
                            f"of {max_rows} rows."
                        ),
                        code="archive_row_limit_exceeded",
                    )
                fields = _parse_hydro_csv_line(line)
                if len(fields) != len(HYDRO_DAILY_COLUMNS):
                    raise ArchiveBackfillError(
                        (
                            f"{name}:{line_number}: expected 10 CODZ fields, "
                            f"got {len(fields)}."
                        ),
                        code="archive_row_invalid",
                    )
                source_row = dict(zip(HYDRO_DAILY_COLUMNS, fields, strict=True))
                if (
                    expected_hydrological_year is not None
                    and source_row["COROKH"].strip() != str(expected_hydrological_year)
                ):
                    raise ArchiveBackfillError(
                        (
                            f"{name}:{line_number}: hydrological year "
                            f"{source_row['COROKH'].strip()!r} does not match "
                            f"archive year {expected_hydrological_year}."
                        ),
                        code="archive_row_invalid",
                    )
                station_code = source_row["PSKDSZS"].strip()
                if not re.fullmatch(r"\d{9}", station_code):
                    raise ArchiveBackfillError(
                        f"{name}:{line_number}: invalid PSKDSZS station code.",
                        code="archive_row_invalid",
                    )
                observed_at = _parse_hydro_daily_date(
                    source_row,
                    source_name=name,
                    line_number=line_number,
                )
                observed_day = observed_at.date()
                if observed_day < observed_from or observed_day > observed_to:
                    continue
                normalized_values = tuple(
                    source_row[column].strip()
                    for column in HYDRO_DAILY_COLUMNS
                )
                row_key = (station_code, observed_at)
                previous = seen_rows.get(row_key)
                if previous is not None:
                    if previous != normalized_values:
                        raise ArchiveBackfillError(
                            (
                                f"{name}:{line_number}: conflicting duplicate for "
                                f"{station_code} on {observed_day.isoformat()}."
                            ),
                            code="archive_conflicting_duplicate",
                        )
                    duplicate_rows += 1
                    continue
                seen_rows[row_key] = normalized_values

                station_name = source_row["PSNZWP"].strip() or station_code
                for raw_field, metric, unit, sentinel in HYDRO_DAILY_METRICS:
                    value, missing_reason = _parse_hydro_value(
                        source_row[raw_field],
                        sentinel=sentinel,
                        source_name=name,
                        line_number=line_number,
                        raw_field=raw_field,
                    )
                    records.append(
                        {
                            "station_id": f"hydro:{station_code}",
                            "station_name": station_name,
                            "source_key": "hydro",
                            "station_type": "hydro",
                            "metric": metric,
                            "value": value,
                            "unit": unit,
                            "observed_at": observed_at,
                            "retrieved_at": imported_at,
                            "missing": value is None,
                            "raw_field": f"{raw_field}:{source_row[raw_field].strip()}",
                            "import_run_id": import_run_id,
                            "import_source_url": source_url,
                            "source_station_id": station_code,
                            "station_mapping_status": None,
                            "station_mapping_version": None,
                            "station_mapping_source_url": None,
                            "station_mapping_retrieved_at": None,
                            "archive_kind": HYDRO_DAILY_ARCHIVE_KIND,
                            "quality_status": (
                                "not_provided_by_source"
                                if value is not None
                                else None
                            ),
                            "missing_reason": missing_reason,
                            "temporal_resolution": "1d",
                            "source_file_sha256": source_file_sha256,
                            "source_file_last_modified": source_file_last_modified,
                        }
                    )

    if duplicate_rows:
        warnings.append(
            f"{source_url}: collapsed {duplicate_rows} identical duplicate row(s)."
        )
    return records, warnings, duplicate_rows


def _parse_hydro_csv_line(line: str) -> list[str]:
    line = line.lstrip("\ufeff")
    delimiter = ";" if line.count(";") > line.count(",") else ","
    fields = next(csv.reader([line], delimiter=delimiter))
    # The 2024 publication wrapped each complete CSV row in one quoted field.
    if len(fields) == 1 and delimiter in fields[0]:
        fields = next(csv.reader([fields[0]], delimiter=delimiter))
    return [field.strip().strip('"') for field in fields]


def _decode_hydro_archive_text(raw: bytes, *, source_name: str) -> str:
    for encoding in ("utf-8-sig", "cp1250"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ArchiveBackfillError(
        f"{source_name}: CODZ text is neither valid UTF-8 nor CP1250.",
        code="archive_encoding_invalid",
    )


def _parse_hydro_daily_date(
    row: dict[str, str],
    *,
    source_name: str,
    line_number: int,
) -> datetime:
    try:
        hydrological_year = int(row["COROKH"])
        hydrological_month = int(row["COMSCH"])
        day = int(row["CODZIEN"])
        calendar_month = int(row["COMSCK"])
    except ValueError as exc:
        raise ArchiveBackfillError(
            f"{source_name}:{line_number}: invalid CODZ date fields.",
            code="archive_row_invalid",
        ) from exc
    if not 1 <= hydrological_month <= 12:
        raise ArchiveBackfillError(
            f"{source_name}:{line_number}: invalid hydrological month.",
            code="archive_row_invalid",
        )
    expected_calendar_month = (
        hydrological_month + 10
        if hydrological_month <= 2
        else hydrological_month - 2
    )
    if calendar_month != expected_calendar_month:
        raise ArchiveBackfillError(
            (
                f"{source_name}:{line_number}: calendar month {calendar_month} "
                f"does not match hydrological month {hydrological_month}."
            ),
            code="archive_row_invalid",
        )
    calendar_year = (
        hydrological_year - 1 if calendar_month in {11, 12} else hydrological_year
    )
    try:
        observed_at = datetime(
            calendar_year,
            calendar_month,
            day,
            tzinfo=UTC,
        )
    except ValueError as exc:
        raise ArchiveBackfillError(
            f"{source_name}:{line_number}: invalid calendar date.",
            code="archive_row_invalid",
        ) from exc
    if (
        _hydrological_year(observed_at.date()) != hydrological_year
        or _hydrological_month_index(observed_at.date()) != hydrological_month
    ):
        raise ArchiveBackfillError(
            f"{source_name}:{line_number}: inconsistent hydrological date.",
            code="archive_row_invalid",
        )
    return observed_at


def _parse_hydro_value(
    raw: str,
    *,
    sentinel: Decimal,
    source_name: str,
    line_number: int,
    raw_field: str,
) -> tuple[float | None, str | None]:
    value = raw.strip()
    if not value or value.upper() == "NULL":
        return None, "source_null"
    try:
        decimal_value = Decimal(value)
    except InvalidOperation as exc:
        raise ArchiveBackfillError(
            f"{source_name}:{line_number}: invalid numeric value in {raw_field}.",
            code="archive_row_invalid",
        ) from exc
    if decimal_value == sentinel:
        return None, "source_sentinel"
    return float(decimal_value), None


def _hydrological_year(day: date) -> int:
    return day.year + 1 if day.month >= 11 else day.year


def _hydrological_month_index(day: date) -> int:
    return day.month - 10 if day.month >= 11 else day.month + 2


def _hydrological_year_bounds(hydrological_year: int) -> tuple[date, date]:
    return date(hydrological_year - 1, 11, 1), date(hydrological_year, 10, 31)


def _hydrological_month_bounds(
    hydrological_year: int,
    hydrological_month: int,
) -> tuple[date, date]:
    if not 1 <= hydrological_month <= 12:
        raise ArchiveBackfillError(
            f"Invalid hydrological month {hydrological_month}.",
            code="archive_file_name_invalid",
        )
    calendar_month = (
        hydrological_month + 10
        if hydrological_month <= 2
        else hydrological_month - 2
    )
    calendar_year = (
        hydrological_year - 1 if calendar_month in {11, 12} else hydrological_year
    )
    return (
        date(calendar_year, calendar_month, 1),
        date(
            calendar_year,
            calendar_month,
            monthrange(calendar_year, calendar_month)[1],
        ),
    )


def _clip_date_range(
    left_from: date,
    left_to: date,
    right_from: date,
    right_to: date,
) -> tuple[date, date] | None:
    clipped_from = max(left_from, right_from)
    clipped_to = min(left_to, right_to)
    return None if clipped_from > clipped_to else (clipped_from, clipped_to)


def parse_synop_daily_zip(
    content: bytes,
    *,
    source_url: str,
    import_run_id: str,
    imported_at: datetime,
    observed_from: date,
    observed_to: date,
    station_mapping: SynopStationMapping | None = None,
    settings: Settings | None = None,
) -> tuple[list[ArchiveObservationRow], list[str]]:
    active_settings = settings or Settings()
    validate_archive_zip(content, active_settings)
    max_entry_bytes = active_settings.archive_zip_entry_max_bytes
    max_total_bytes = active_settings.archive_zip_total_uncompressed_max_bytes
    max_rows = active_settings.archive_max_rows_per_file
    mapping = station_mapping or SynopStationMapping.load()
    warnings: list[str] = []
    warned_unmapped: set[str] = set()
    records: list[ArchiveObservationRow] = []
    rows_seen = 0
    total_uncompressed = 0
    with zipfile.ZipFile(BytesIO(content)) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            return [], [f"{source_url}: no CSV files found in ZIP."]
        for name in csv_names:
            raw = archive.read(name)
            total_uncompressed += len(raw)
            if len(raw) > max_entry_bytes:
                raise ArchiveBackfillError(
                    (
                        f"Archive ZIP entry {name!r} expanded to "
                        f"{len(raw)} bytes; limit is {max_entry_bytes} bytes."
                    ),
                    code="archive_zip_entry_too_large",
                )
            if total_uncompressed > max_total_bytes:
                raise ArchiveBackfillError(
                    (
                        "Archive ZIP expanded to "
                        f"{total_uncompressed} total bytes; limit is "
                        f"{max_total_bytes} bytes."
                    ),
                    code="archive_zip_uncompressed_too_large",
                )
            text = _decode_archive_text(raw)
            reader = csv.DictReader(StringIO(text), fieldnames=SYNOP_DAILY_COLUMNS)
            for line_number, row in enumerate(reader, start=1):
                rows_seen += 1
                if rows_seen > max_rows:
                    raise ArchiveBackfillError(
                        (
                            f"Archive CSV row count exceeds the configured limit "
                            f"of {max_rows} rows."
                        ),
                        code="archive_row_limit_exceeded",
                    )
                observed_at = _parse_synop_daily_date(row)
                if observed_at is None:
                    warnings.append(f"{name}:{line_number}: invalid observation date.")
                    continue
                observed_day = observed_at.date()
                if observed_day < observed_from or observed_day > observed_to:
                    continue
                station_id = str(row.get("NSP") or "").strip().strip('"')
                if not station_id:
                    warnings.append(f"{name}:{line_number}: missing station id.")
                    continue
                resolution = mapping.resolve(station_id)
                if resolution.mapping_status != "mapped" and station_id not in warned_unmapped:
                    warnings.append(
                        f"{name}:{line_number}: NSP {station_id} has mapping status "
                        f"{resolution.mapping_status}; stored as {resolution.station_id}."
                    )
                    warned_unmapped.add(station_id)
                station_name = str(row.get("POST") or station_id).strip()
                for field, status_field, metric, unit in SYNOP_DAILY_METRICS:
                    value = _parse_optional_float(row.get(field))
                    status = str(row.get(status_field) or "").strip()
                    missing = status == "8"
                    if missing:
                        value = None
                    if value is None and not missing and status != "9":
                        missing = True
                    records.append(
                        {
                            "station_id": resolution.station_id,
                            "station_name": station_name,
                            "source_key": "synop",
                            "station_type": "synop",
                            "metric": metric,
                            "value": value,
                            "unit": unit,
                            "observed_at": observed_at,
                            "retrieved_at": imported_at,
                            "missing": missing,
                            "raw_field": f"{field}/{status_field}:{status or 'blank'}",
                            "import_run_id": import_run_id,
                            "import_source_url": source_url,
                            "source_station_id": resolution.source_station_id,
                            "station_mapping_status": resolution.mapping_status,
                            "station_mapping_version": resolution.mapping_version,
                            "station_mapping_source_url": resolution.mapping_source_url,
                            "station_mapping_retrieved_at": (
                                resolution.mapping_retrieved_at
                            ),
                            "archive_kind": "synop_daily",
                            "temporal_resolution": "1d",
                        }
                    )
    return records, warnings


def _synop_file_may_overlap(filename: str, observed_from: date, observed_to: date) -> bool:
    monthly = re.fullmatch(r"(?P<year>\d{4})_(?P<month>\d{2})_s\.zip", filename)
    if monthly:
        file_year = int(monthly.group("year"))
        file_month = int(monthly.group("month"))
        last_day = monthrange(file_year, file_month)[1]
        file_start = date(file_year, file_month, 1)
        file_end = date(file_year, file_month, last_day)
        return file_start <= observed_to and file_end >= observed_from
    yearly_station = re.fullmatch(r"(?P<year>\d{4})_[^/]+_s\.zip", filename)
    if yearly_station:
        file_year = int(yearly_station.group("year"))
        return observed_from.year <= file_year <= observed_to.year
    return True


def _decode_archive_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1250", "iso-8859-2"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp1250", errors="replace")


def _parse_synop_daily_date(row: dict[str, str | None]) -> datetime | None:
    try:
        return datetime(
            int(str(row.get("ROK") or "")),
            int(str(row.get("MC") or "")),
            int(str(row.get("DZ") or "")),
            tzinfo=UTC,
        )
    except ValueError:
        return None


def _parse_optional_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None
