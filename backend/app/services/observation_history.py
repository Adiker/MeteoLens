"""Observation history service helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from app.db.repository import Interval, ObservationRepository
from app.normalization.models import Observation, Station

_repository = ObservationRepository()


def persist_station(station: Station) -> int:
    return _repository.persist_station_observations(station)


def prune_history(*, retention_days: int) -> int:
    return _repository.prune_older_than(retention_days=retention_days)


def query_station_history(
    *,
    station_id: str,
    metric: str | None = None,
    observed_from: datetime | None = None,
    observed_to: datetime | None = None,
    interval: Interval = "raw",
    limit: int = 500,
) -> list[dict[str, Any]]:
    return _repository.query_observations(
        station_id=station_id,
        metric=metric,
        observed_from=observed_from,
        observed_to=observed_to,
        interval=interval,
        limit=limit,
    )


def snapshot_observations(station: Station) -> list[dict[str, Any]]:
    return [
        _observation_payload(observation, station.source.retrieved_at)
        for observation in station.observations
    ]


def _data_delay_seconds(observed_at: datetime | None, retrieved_at: datetime) -> int | None:
    if observed_at is None:
        return None
    return max(0, round((retrieved_at - observed_at).total_seconds()))


def _observation_payload(
    observation: Observation,
    retrieved_at: datetime,
) -> dict[str, Any]:
    payload = observation.model_dump(mode="json")
    payload["data_delay_seconds"] = _data_delay_seconds(observation.observed_at, retrieved_at)
    return payload


def compare_stations(
    *,
    station_ids: list[str],
    metric: str,
    observed_from: datetime | None = None,
    observed_to: datetime | None = None,
    interval: Interval = "raw",
    limit: int = 200,
) -> dict[str, list[dict[str, Any]]]:
    return _repository.compare_stations(
        station_ids=station_ids,
        metric=metric,
        observed_from=observed_from,
        observed_to=observed_to,
        interval=interval,
        limit=limit,
    )


def rankings(
    *,
    metric: str,
    direction: Literal["highest", "lowest"],
    station_type: str | None = None,
    observed_from: datetime | None = None,
    observed_to: datetime | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    return _repository.rankings(
        metric=metric,
        direction=direction,
        station_type=station_type,
        observed_from=observed_from,
        observed_to=observed_to,
        limit=limit,
    )
