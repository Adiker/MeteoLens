"""Bounded IMGW archive backfill importers."""

from __future__ import annotations

import csv
import json
import re
import time
import zipfile
from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from io import BytesIO, StringIO
from uuid import uuid4

import httpx

from app.core.config import Settings
from app.db.engine import get_engine, init_db
from app.db.repository import ArchiveObservationRow, ObservationRepository, _iso
from app.normalization.models import ATTRIBUTION, PROCESSED_NOTICE

SYNOP_DAILY_BASE_PATH = (
    "/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/synop"
)

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
        files: list[ArchiveFile] = []
        rows_seen = 0
        observations_seen = 0
        inserted = 0
        updated = 0
        unchanged = 0
        parser_warnings: list[str] = []
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
                    content = self._fetch_file(client, archive_file)
                    parsed_rows, warnings = parse_synop_daily_zip(
                        content,
                        source_url=archive_file.url,
                        import_run_id=run_id,
                        imported_at=datetime.now(UTC),
                        observed_from=observed_from,
                        observed_to=observed_to,
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
                raise
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

    def _fetch_file(self, client: httpx.Client, archive_file: ArchiveFile) -> bytes:
        response = client.get(archive_file.url)
        response.raise_for_status()
        return response.content

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


def parse_synop_daily_zip(
    content: bytes,
    *,
    source_url: str,
    import_run_id: str,
    imported_at: datetime,
    observed_from: date,
    observed_to: date,
) -> tuple[list[ArchiveObservationRow], list[str]]:
    warnings: list[str] = []
    records: list[ArchiveObservationRow] = []
    with zipfile.ZipFile(BytesIO(content)) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            return [], [f"{source_url}: no CSV files found in ZIP."]
        for name in csv_names:
            raw = archive.read(name)
            text = _decode_archive_text(raw)
            reader = csv.DictReader(StringIO(text), fieldnames=SYNOP_DAILY_COLUMNS)
            for line_number, row in enumerate(reader, start=1):
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
                            "station_id": f"synop:{station_id}",
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
