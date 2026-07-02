"""Database engine and schema initialization."""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS observation_history (
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

CREATE INDEX IF NOT EXISTS idx_obs_station_metric_time
    ON observation_history(station_id, metric, observed_at);

CREATE INDEX IF NOT EXISTS idx_obs_metric_time
    ON observation_history(metric, observed_at);

CREATE INDEX IF NOT EXISTS idx_obs_station_type
    ON observation_history(station_type);
"""


def database_path_from_url(database_url: str) -> Path:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise ValueError(f"Only sqlite URLs are supported in MVP, got {parsed.scheme}")
    if parsed.path in {":memory:", "/:memory:"}:
        return Path(":memory:")
    if database_url.startswith("sqlite:////"):
        return Path(parsed.path)
    raw_path = parsed.path.lstrip("/")
    if raw_path == ":memory:":
        return Path(":memory:")
    path = Path(raw_path)
    if path.is_absolute():
        return Path(parsed.path)
    return path


@lru_cache
def get_engine() -> sqlite3.Connection:
    settings = get_settings()
    path = database_path_from_url(settings.database_url)
    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    connection = get_engine()
    connection.executescript(SCHEMA_SQL)
    connection.commit()


def reset_engine_cache() -> None:
    get_engine.cache_clear()
