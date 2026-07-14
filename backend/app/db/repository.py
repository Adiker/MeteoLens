"""Observation history persistence and queries."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from app.db.engine import get_engine, init_db
from app.imgw.parsers.utils import SOURCE_TIMEZONE
from app.normalization.models import Station

if TYPE_CHECKING:
    from app.imgw.station_mapping import SynopStationMapping

Interval = Literal["raw", "10m", "1h", "1d"]
ObservationOrigin = Literal["live_refresh", "archive_import", "mixed"]

RANKING_METRICS: dict[str, tuple[str, ...]] = {
    "temperature": ("temperature", "air_temperature", "ground_temperature"),
    "wind_speed": ("wind_speed", "wind_average_speed", "wind_max_speed", "wind_gust_10min"),
    "precipitation": ("precipitation_sum", "precipitation_10min"),
    "water_level": ("water_level",),
}


class ArchiveObservationRow(TypedDict):
    station_id: str
    station_name: str
    source_key: str
    station_type: str
    metric: str
    value: float | None
    unit: str | None
    observed_at: datetime
    retrieved_at: datetime
    missing: bool
    raw_field: str
    import_run_id: str
    import_source_url: str
    source_station_id: str
    station_mapping_status: str
    station_mapping_version: str
    station_mapping_source_url: str
    station_mapping_retrieved_at: datetime


class ArchivePersistSummary(TypedDict):
    inserted: int
    updated: int
    unchanged: int


class ArchiveReconciliationSummary(TypedDict):
    migrated: int
    deduplicated: int
    skipped: int


def _iso(dt: datetime) -> str:
    # Naive datetimes (e.g. unqualified `from`/`to` query params) are IMGW
    # local time, matching the snapshot query path's _normalize_query_datetime.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SOURCE_TIMEZONE)
    return dt.astimezone(UTC).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class ObservationRepository:
    def reconcile_legacy_archive_station_ids(
        self,
        mapping: SynopStationMapping,
    ) -> ArchiveReconciliationSummary:
        """Upgrade pre-mapping archive rows through the reviewed artifact only."""
        init_db()
        connection = get_engine()
        summary: ArchiveReconciliationSummary = {
            "migrated": 0,
            "deduplicated": 0,
            "skipped": 0,
        }
        rows = connection.execute(
            """
            SELECT id, station_id, metric, observed_at
            FROM observation_history
            WHERE origin = 'archive_import' AND source_station_id IS NULL
            ORDER BY id
            """
        ).fetchall()
        for row in rows:
            station_id = str(row["station_id"])
            if station_id.startswith("synop:"):
                nsp = station_id.removeprefix("synop:")
            elif station_id.startswith("synop-archive:"):
                nsp = station_id.removeprefix("synop-archive:")
            else:
                summary["skipped"] += 1
                continue
            if len(nsp) != 9 or not nsp.isdigit():
                summary["skipped"] += 1
                continue
            resolution = mapping.resolve(nsp)
            existing = connection.execute(
                """
                SELECT id
                FROM observation_history
                WHERE station_id = ? AND metric = ? AND observed_at = ?
                    AND origin = 'archive_import' AND id != ?
                """,
                (
                    resolution.station_id,
                    row["metric"],
                    row["observed_at"],
                    row["id"],
                ),
            ).fetchone()
            if existing is not None:
                connection.execute(
                    "DELETE FROM observation_history WHERE id = ?", (row["id"],)
                )
                summary["deduplicated"] += 1
                continue
            connection.execute(
                """
                UPDATE observation_history
                SET station_id = ?, source_station_id = ?,
                    station_mapping_status = ?, station_mapping_version = ?,
                    station_mapping_source_url = ?, station_mapping_retrieved_at = ?
                WHERE id = ?
                """,
                (
                    resolution.station_id,
                    resolution.source_station_id,
                    resolution.mapping_status,
                    resolution.mapping_version,
                    resolution.mapping_source_url,
                    _iso(resolution.mapping_retrieved_at),
                    row["id"],
                ),
            )
            summary["migrated"] += 1
        connection.commit()
        return summary

    def persist_station_observations(self, station: Station) -> int:
        init_db()
        connection = get_engine()
        inserted = 0
        for observation in station.observations:
            if observation.observed_at is None:
                continue
            cursor = connection.execute(
                """
                INSERT INTO observation_history (
                    station_id, station_name, source_key, station_type,
                    metric, value, unit, observed_at, retrieved_at,
                    missing, raw_field, origin, import_run_id, import_source_url,
                    source_station_id, station_mapping_status,
                    station_mapping_version, station_mapping_source_url,
                    station_mapping_retrieved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(station_id, metric, observed_at, origin) DO UPDATE SET
                    station_name = excluded.station_name,
                    source_key = excluded.source_key,
                    station_type = excluded.station_type,
                    value = excluded.value,
                    unit = excluded.unit,
                    retrieved_at = excluded.retrieved_at,
                    missing = excluded.missing,
                    raw_field = excluded.raw_field,
                    origin = excluded.origin,
                    import_run_id = excluded.import_run_id,
                    import_source_url = excluded.import_source_url,
                    source_station_id = excluded.source_station_id,
                    station_mapping_status = excluded.station_mapping_status,
                    station_mapping_version = excluded.station_mapping_version,
                    station_mapping_source_url = excluded.station_mapping_source_url,
                    station_mapping_retrieved_at = excluded.station_mapping_retrieved_at
                """,
                (
                    station.id,
                    station.name,
                    station.source_key,
                    station.station_type,
                    observation.metric,
                    observation.value,
                    observation.unit,
                    _iso(observation.observed_at),
                    _iso(station.source.retrieved_at),
                    1 if observation.missing else 0,
                    observation.raw_field,
                    "live_refresh",
                    None,
                    station.source.url,
                    station.source_id,
                    None,
                    None,
                    None,
                    None,
                ),
            )
            if cursor.rowcount:
                inserted += 1
        connection.commit()
        return inserted

    def persist_archive_observations(
        self,
        observations: list[ArchiveObservationRow],
    ) -> ArchivePersistSummary:
        init_db()
        connection = get_engine()
        summary: ArchivePersistSummary = {"inserted": 0, "updated": 0, "unchanged": 0}
        for observation in observations:
            key = (
                observation["station_id"],
                observation["metric"],
                _iso(observation["observed_at"]),
            )
            existing = connection.execute(
                """
                SELECT value, unit, retrieved_at, missing, raw_field, origin,
                       import_run_id, import_source_url, source_station_id,
                       station_mapping_status, station_mapping_version,
                       station_mapping_source_url, station_mapping_retrieved_at
                FROM observation_history
                WHERE station_id = ? AND metric = ? AND observed_at = ?
                    AND origin = 'archive_import'
                """,
                key,
            ).fetchone()
            cursor = connection.execute(
                """
                INSERT INTO observation_history (
                    station_id, station_name, source_key, station_type,
                    metric, value, unit, observed_at, retrieved_at,
                    missing, raw_field, origin, import_run_id, import_source_url,
                    source_station_id, station_mapping_status,
                    station_mapping_version, station_mapping_source_url,
                    station_mapping_retrieved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(station_id, metric, observed_at, origin) DO UPDATE SET
                    station_name = excluded.station_name,
                    source_key = excluded.source_key,
                    station_type = excluded.station_type,
                    value = excluded.value,
                    unit = excluded.unit,
                    retrieved_at = excluded.retrieved_at,
                    missing = excluded.missing,
                    raw_field = excluded.raw_field,
                    origin = excluded.origin,
                    import_run_id = excluded.import_run_id,
                    import_source_url = excluded.import_source_url,
                    source_station_id = excluded.source_station_id,
                    station_mapping_status = excluded.station_mapping_status,
                    station_mapping_version = excluded.station_mapping_version,
                    station_mapping_source_url = excluded.station_mapping_source_url,
                    station_mapping_retrieved_at = excluded.station_mapping_retrieved_at
                WHERE
                    value IS NOT excluded.value OR
                    unit IS NOT excluded.unit OR
                    retrieved_at IS NOT excluded.retrieved_at OR
                    missing IS NOT excluded.missing OR
                    raw_field IS NOT excluded.raw_field OR
                    origin IS NOT excluded.origin OR
                    import_run_id IS NOT excluded.import_run_id OR
                    import_source_url IS NOT excluded.import_source_url OR
                    source_station_id IS NOT excluded.source_station_id OR
                    station_mapping_status IS NOT excluded.station_mapping_status OR
                    station_mapping_version IS NOT excluded.station_mapping_version OR
                    station_mapping_source_url IS NOT excluded.station_mapping_source_url OR
                    station_mapping_retrieved_at IS NOT excluded.station_mapping_retrieved_at
                """,
                (
                    observation["station_id"],
                    observation["station_name"],
                    observation["source_key"],
                    observation["station_type"],
                    observation["metric"],
                    observation["value"],
                    observation["unit"],
                    key[2],
                    _iso(observation["retrieved_at"]),
                    1 if observation["missing"] else 0,
                    observation["raw_field"],
                    "archive_import",
                    observation["import_run_id"],
                    observation["import_source_url"],
                    observation["source_station_id"],
                    observation["station_mapping_status"],
                    observation["station_mapping_version"],
                    observation["station_mapping_source_url"],
                    _iso(observation["station_mapping_retrieved_at"]),
                ),
            )
            if existing is None:
                summary["inserted"] += 1
            elif cursor.rowcount:
                summary["updated"] += 1
            else:
                summary["unchanged"] += 1
        connection.commit()
        return summary

    def prune_older_than(self, *, retention_days: int) -> int:
        if retention_days <= 0:
            return 0
        cutoff = _iso(datetime.now(UTC) - timedelta(days=retention_days))
        connection = get_engine()
        cursor = connection.execute(
            "DELETE FROM observation_history WHERE observed_at < ?",
            (cutoff,),
        )
        connection.commit()
        return cursor.rowcount

    def query_observations(
        self,
        *,
        station_id: str,
        metric: str | None = None,
        observed_from: datetime | None = None,
        observed_to: datetime | None = None,
        interval: Interval = "raw",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        init_db()
        clauses = ["station_id = ?"]
        params: list[Any] = [station_id]
        if metric is not None:
            clauses.append("metric = ?")
            params.append(metric)
        if observed_from is not None:
            clauses.append("observed_at >= ?")
            params.append(_iso(observed_from))
        if observed_to is not None:
            clauses.append("observed_at <= ?")
            params.append(_iso(observed_to))

        where = " AND ".join(clauses)
        newest_first = observed_from is None
        order_direction = "DESC" if newest_first else "ASC"
        connection = get_engine()
        rows = connection.execute(
            f"""
            SELECT station_id, station_name, source_key, station_type,
                   metric, value, unit, observed_at, retrieved_at,
                   missing, raw_field, origin, import_run_id, import_source_url,
                   source_station_id, station_mapping_status,
                   station_mapping_version, station_mapping_source_url,
                   station_mapping_retrieved_at
            FROM observation_history
            WHERE {where}
            ORDER BY observed_at {order_direction}
            LIMIT ?
            """,
            (*params, limit * 10 if interval != "raw" else limit),
        ).fetchall()

        records = [_row_to_observation(row) for row in rows]
        if newest_first:
            records.reverse()
        if interval == "raw":
            return records[-limit:]
        return _aggregate_observations(records, interval=interval, limit=limit)

    def compare_stations(
        self,
        *,
        station_ids: list[str],
        metric: str,
        observed_from: datetime | None = None,
        observed_to: datetime | None = None,
        interval: Interval = "raw",
        limit: int = 200,
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            station_id: self.query_observations(
                station_id=station_id,
                metric=metric,
                observed_from=observed_from,
                observed_to=observed_to,
                interval=interval,
                limit=limit,
            )
            for station_id in station_ids
        }

    def rankings(
        self,
        *,
        metric: str,
        direction: Literal["highest", "lowest"],
        station_type: str | None = None,
        observed_from: datetime | None = None,
        observed_to: datetime | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        init_db()
        metric_keys = RANKING_METRICS.get(metric, (metric,))
        placeholders = ", ".join("?" for _ in metric_keys)
        clauses = [f"metric IN ({placeholders})", "missing = 0", "value IS NOT NULL"]
        params: list[Any] = list(metric_keys)
        if station_type is not None:
            clauses.append("station_type = ?")
            params.append(station_type)
        if observed_from is not None:
            clauses.append("observed_at >= ?")
            params.append(_iso(observed_from))
        if observed_to is not None:
            clauses.append("observed_at <= ?")
            params.append(_iso(observed_to))

        where = " AND ".join(clauses)
        connection = get_engine()
        rows = connection.execute(
            f"""
            SELECT station_id, station_name, source_key, station_type,
                   metric, value, unit, observed_at, retrieved_at,
                   missing, raw_field, origin, import_run_id, import_source_url,
                   source_station_id, station_mapping_status,
                   station_mapping_version, station_mapping_source_url,
                   station_mapping_retrieved_at
            FROM observation_history
            WHERE {where}
            ORDER BY observed_at DESC
            """,
            params,
        ).fetchall()

        best_by_station: dict[str, dict[str, Any]] = {}
        for row in rows:
            observation = _row_to_observation(row)
            station_id = observation["station_id"]
            existing = best_by_station.get(station_id)
            if existing is None:
                best_by_station[station_id] = observation
                continue
            is_better = (
                observation["value"] > existing["value"]
                if direction == "highest"
                else observation["value"] < existing["value"]
            )
            if is_better:
                best_by_station[station_id] = observation

        ranked = sorted(
            best_by_station.values(),
            key=lambda item: item["value"],
            reverse=direction == "highest",
        )
        return ranked[:limit]

    def series_origin_summary(
        self,
        *,
        station_id: str,
        metric: str | None = None,
        observed_from: datetime | None = None,
        observed_to: datetime | None = None,
    ) -> dict[str, Any]:
        init_db()
        clauses = ["station_id = ?"]
        params: list[Any] = [station_id]
        if metric is not None:
            clauses.append("metric = ?")
            params.append(metric)
        if observed_from is not None:
            clauses.append("observed_at >= ?")
            params.append(_iso(observed_from))
        if observed_to is not None:
            clauses.append("observed_at <= ?")
            params.append(_iso(observed_to))

        rows = get_engine().execute(
            f"""
            SELECT origin, COUNT(*) AS count
            FROM observation_history
            WHERE {" AND ".join(clauses)}
            GROUP BY origin
            """,
            params,
        ).fetchall()
        counts = {row["origin"]: row["count"] for row in rows}
        if len(counts) > 1:
            series_origin: ObservationOrigin = "mixed"
        elif "archive_import" in counts:
            series_origin = "archive_import"
        else:
            series_origin = "live_refresh"
        return {"series_origin": series_origin, "origin_counts": counts}

    def station_history_summary(self, station_id: str) -> dict[str, Any] | None:
        init_db()
        row = get_engine().execute(
            """
            SELECT station_id, station_name, source_key, station_type,
                   MIN(observed_at) AS first_observed_at,
                   MAX(observed_at) AS latest_observed_at,
                   COUNT(*) AS observation_count
            FROM observation_history
            WHERE station_id = ?
            GROUP BY station_id, station_name, source_key, station_type
            ORDER BY MAX(observed_at) DESC
            LIMIT 1
            """,
            (station_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "station_id": row["station_id"],
            "station_name": row["station_name"],
            "source_key": row["source_key"],
            "station_type": row["station_type"],
            "first_observed_at": row["first_observed_at"],
            "latest_observed_at": row["latest_observed_at"],
            "observation_count": row["observation_count"],
        }


def _row_to_observation(row: Any) -> dict[str, Any]:
    observed_at = _parse_iso(row["observed_at"])
    retrieved_at = _parse_iso(row["retrieved_at"])
    return {
        "metric": row["metric"],
        "value": row["value"],
        "unit": row["unit"],
        "observed_at": observed_at.isoformat(),
        "retrieved_at": retrieved_at.isoformat(),
        "data_delay_seconds": max(
            0, round((retrieved_at - observed_at).total_seconds())
        ),
        "missing": bool(row["missing"]),
        "raw_field": row["raw_field"],
        "origin": row["origin"],
        "import_run_id": row["import_run_id"],
        "import_source_url": row["import_source_url"],
        "source_station_id": row["source_station_id"],
        "station_mapping_status": row["station_mapping_status"],
        "station_mapping_version": row["station_mapping_version"],
        "station_mapping_source_url": row["station_mapping_source_url"],
        "station_mapping_retrieved_at": row["station_mapping_retrieved_at"],
        "station_id": row["station_id"],
        "station_name": row["station_name"],
        "station_type": row["station_type"],
        "source_key": row["source_key"],
    }


def _bucket_key(observed_at: datetime, interval: Interval) -> str:
    if interval == "10m":
        minute = (observed_at.minute // 10) * 10
        bucket = observed_at.replace(minute=minute, second=0, microsecond=0)
    elif interval == "1h":
        bucket = observed_at.replace(minute=0, second=0, microsecond=0)
    elif interval == "1d":
        bucket = observed_at.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        bucket = observed_at
    return bucket.isoformat()


def _aggregate_observations(
    records: list[dict[str, Any]],
    *,
    interval: Interval,
    limit: int,
) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        observed_at = _parse_iso(record["observed_at"])
        buckets[(_bucket_key(observed_at, interval), record["metric"])].append(record)

    aggregated: list[dict[str, Any]] = []
    for bucket_key, _metric in sorted(buckets):
        points = buckets[(bucket_key, _metric)]
        values = [point["value"] for point in points if point["value"] is not None]
        if not values:
            continue
        latest = points[-1]
        origins = {point.get("origin") for point in points}
        origin = "mixed" if len(origins) > 1 else latest.get("origin", "live_refresh")
        aggregated.append(
            {
                **latest,
                "value": sum(values) / len(values),
                "observed_at": bucket_key,
                "aggregated_from": len(points),
                "interval": interval,
                "origin": origin,
                "import_run_id": None if origin == "mixed" else latest.get("import_run_id"),
                "import_source_url": None
                if origin == "mixed"
                else latest.get("import_source_url"),
                "source_station_id": None
                if origin == "mixed"
                else latest.get("source_station_id"),
                "station_mapping_status": None
                if origin == "mixed"
                else latest.get("station_mapping_status"),
                "station_mapping_version": None
                if origin == "mixed"
                else latest.get("station_mapping_version"),
                "station_mapping_source_url": None
                if origin == "mixed"
                else latest.get("station_mapping_source_url"),
                "station_mapping_retrieved_at": None
                if origin == "mixed"
                else latest.get("station_mapping_retrieved_at"),
            }
        )
    return aggregated[-limit:]
