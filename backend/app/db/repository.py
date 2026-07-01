"""Observation history persistence and queries."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.db.engine import get_engine, init_db
from app.normalization.models import Station

Interval = Literal["raw", "10m", "1h", "1d"]

RANKING_METRICS: dict[str, tuple[str, ...]] = {
    "temperature": ("temperature", "temperatura", "temperatura_powietrza"),
    "wind_speed": ("wind_speed", "predkosc_wiatru", "wiatr"),
    "precipitation": ("precipitation", "suma_opadu", "opad"),
    "water_level": ("water_level", "stan_wody"),
}


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class ObservationRepository:
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
                    missing, raw_field
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(station_id, metric, observed_at) DO UPDATE SET
                    station_name = excluded.station_name,
                    source_key = excluded.source_key,
                    station_type = excluded.station_type,
                    value = excluded.value,
                    unit = excluded.unit,
                    retrieved_at = excluded.retrieved_at,
                    missing = excluded.missing,
                    raw_field = excluded.raw_field
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
                ),
            )
            if cursor.rowcount:
                inserted += 1
        connection.commit()
        return inserted

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
        connection = get_engine()
        rows = connection.execute(
            f"""
            SELECT station_id, station_name, source_key, station_type,
                   metric, value, unit, observed_at, retrieved_at,
                   missing, raw_field
            FROM observation_history
            WHERE {where}
            ORDER BY observed_at ASC
            LIMIT ?
            """,
            (*params, limit * 10 if interval != "raw" else limit),
        ).fetchall()

        records = [_row_to_observation(row) for row in rows]
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
                   missing, raw_field
            FROM observation_history
            WHERE {where}
            ORDER BY observed_at DESC
            """,
            params,
        ).fetchall()

        best_by_station: dict[str, dict[str, Any]] = {}
        for row in rows:
            station_id = row["station_id"]
            if station_id in best_by_station:
                continue
            best_by_station[station_id] = _row_to_observation(row)

        ranked = sorted(
            best_by_station.values(),
            key=lambda item: item["value"],
            reverse=direction == "highest",
        )
        return ranked[:limit]


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
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        observed_at = _parse_iso(record["observed_at"])
        buckets[_bucket_key(observed_at, interval)].append(record)

    aggregated: list[dict[str, Any]] = []
    for bucket_key in sorted(buckets):
        points = buckets[bucket_key]
        values = [point["value"] for point in points if point["value"] is not None]
        if not values:
            continue
        latest = points[-1]
        aggregated.append(
            {
                **latest,
                "value": sum(values) / len(values),
                "observed_at": bucket_key,
                "aggregated_from": len(points),
                "interval": interval,
            }
        )
    return aggregated[-limit:]
