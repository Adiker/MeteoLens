"""Database engine and schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock, get_ident
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
    origin TEXT NOT NULL DEFAULT 'live_refresh',
    import_run_id TEXT,
    import_source_url TEXT,
    source_station_id TEXT,
    station_mapping_status TEXT,
    station_mapping_version TEXT,
    station_mapping_source_url TEXT,
    station_mapping_retrieved_at TEXT,
    archive_kind TEXT,
    quality_status TEXT,
    missing_reason TEXT,
    temporal_resolution TEXT,
    source_file_sha256 TEXT,
    source_file_last_modified TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(station_id, metric, observed_at, origin)
);

CREATE INDEX IF NOT EXISTS idx_obs_station_metric_time
    ON observation_history(station_id, metric, observed_at);

CREATE INDEX IF NOT EXISTS idx_obs_metric_time
    ON observation_history(metric, observed_at);

CREATE INDEX IF NOT EXISTS idx_obs_station_type
    ON observation_history(station_type);

CREATE TABLE IF NOT EXISTS archive_import_runs (
    id TEXT PRIMARY KEY,
    source_key TEXT NOT NULL,
    archive_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    observed_from TEXT NOT NULL,
    observed_to TEXT NOT NULL,
    files_total INTEGER NOT NULL DEFAULT 0,
    files_processed INTEGER NOT NULL DEFAULT 0,
    rows_seen INTEGER NOT NULL DEFAULT 0,
    observations_seen INTEGER NOT NULL DEFAULT 0,
    observations_inserted INTEGER NOT NULL DEFAULT 0,
    observations_updated INTEGER NOT NULL DEFAULT 0,
    observations_unchanged INTEGER NOT NULL DEFAULT 0,
    observations_deleted INTEGER NOT NULL DEFAULT 0,
    duplicate_rows INTEGER NOT NULL DEFAULT 0,
    parser_warnings TEXT NOT NULL DEFAULT '[]',
    errors TEXT NOT NULL DEFAULT '[]',
    attribution TEXT NOT NULL,
    processed_notice TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS archive_import_run_files (
    run_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    file_name TEXT NOT NULL,
    hydrological_year INTEGER,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    source_file_sha256 TEXT,
    source_file_last_modified TEXT,
    rows_seen INTEGER NOT NULL DEFAULT 0,
    observations_seen INTEGER NOT NULL DEFAULT 0,
    observations_inserted INTEGER NOT NULL DEFAULT 0,
    observations_updated INTEGER NOT NULL DEFAULT 0,
    observations_unchanged INTEGER NOT NULL DEFAULT 0,
    observations_deleted INTEGER NOT NULL DEFAULT 0,
    duplicate_rows INTEGER NOT NULL DEFAULT 0,
    parser_warnings TEXT NOT NULL DEFAULT '[]',
    errors TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (run_id, source_url),
    FOREIGN KEY (run_id) REFERENCES archive_import_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS warning_histories (
    history_id TEXT PRIMARY KEY,
    identity_key TEXT NOT NULL,
    generation INTEGER NOT NULL DEFAULT 1,
    identity_status TEXT NOT NULL,
    source_key TEXT NOT NULL,
    source_id TEXT,
    warning_type TEXT NOT NULL,
    office TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    history_started_at TEXT NOT NULL,
    absent_complete_snapshots INTEGER NOT NULL DEFAULT 0,
    current_version_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(identity_key, generation)
);

CREATE TABLE IF NOT EXISTS warning_identity_generations (
    identity_hash TEXT PRIMARY KEY,
    last_generation INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS warning_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    completeness TEXT NOT NULL,
    first_retrieved_at TEXT NOT NULL,
    last_retrieved_at TEXT NOT NULL,
    seen_count INTEGER NOT NULL DEFAULT 1,
    parser_warnings TEXT NOT NULL DEFAULT '[]',
    exact_duplicate_count INTEGER NOT NULL DEFAULT 0,
    conflicting_duplicate_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS warning_versions (
    version_id TEXT PRIMARY KEY,
    history_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    event_name TEXT NOT NULL,
    level INTEGER,
    probability INTEGER,
    valid_from TEXT,
    valid_to TEXT,
    published_at TEXT,
    office TEXT,
    missing_fields TEXT NOT NULL DEFAULT '[]',
    normalized_payload TEXT NOT NULL,
    raw_payload TEXT NOT NULL,
    source_metadata TEXT NOT NULL,
    FOREIGN KEY (history_id) REFERENCES warning_histories(history_id) ON DELETE CASCADE,
    UNIQUE(history_id, content_hash)
);

CREATE TABLE IF NOT EXISTS warning_version_areas (
    version_id TEXT NOT NULL,
    area_type TEXT NOT NULL,
    code TEXT NOT NULL,
    label TEXT,
    region TEXT,
    PRIMARY KEY (version_id, area_type, code),
    FOREIGN KEY (version_id) REFERENCES warning_versions(version_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS warning_snapshot_members (
    snapshot_id INTEGER NOT NULL,
    history_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    duplicate_status TEXT NOT NULL DEFAULT 'unique',
    PRIMARY KEY (snapshot_id, history_id, version_id),
    FOREIGN KEY (snapshot_id) REFERENCES warning_snapshots(id) ON DELETE CASCADE,
    FOREIGN KEY (history_id) REFERENCES warning_histories(history_id) ON DELETE CASCADE,
    FOREIGN KEY (version_id) REFERENCES warning_versions(version_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS warning_events (
    event_id TEXT PRIMARY KEY,
    history_id TEXT NOT NULL,
    source_key TEXT NOT NULL,
    warning_type TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    effective_at TEXT,
    change_kinds TEXT NOT NULL,
    changed_fields TEXT NOT NULL DEFAULT '[]',
    classification_basis TEXT NOT NULL,
    confidence TEXT NOT NULL,
    from_version_id TEXT,
    to_version_id TEXT,
    snapshot_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (history_id) REFERENCES warning_histories(history_id) ON DELETE CASCADE,
    FOREIGN KEY (from_version_id) REFERENCES warning_versions(version_id) ON DELETE SET NULL,
    FOREIGN KEY (to_version_id) REFERENCES warning_versions(version_id) ON DELETE SET NULL,
    FOREIGN KEY (snapshot_id) REFERENCES warning_snapshots(id) ON DELETE SET NULL
);
"""

POST_MIGRATION_STATEMENTS = (
    """
    CREATE INDEX IF NOT EXISTS idx_obs_station_metric_time
        ON observation_history(station_id, metric, observed_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_obs_metric_time
        ON observation_history(metric, observed_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_obs_station_type
        ON observation_history(station_type)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_obs_origin
        ON observation_history(origin)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_obs_archive_kind_time
        ON observation_history(archive_kind, observed_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_archive_run_files_run
        ON archive_import_run_files(run_id, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_warning_histories_identity
        ON warning_histories(identity_key, generation)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_warning_histories_source_status
        ON warning_histories(source_key, status, last_observed_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_warning_versions_history_time
        ON warning_versions(history_id, first_seen_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_warning_version_areas_code
        ON warning_version_areas(code, version_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_warning_snapshots_source_time
        ON warning_snapshots(source_key, last_retrieved_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_warning_events_feed
        ON warning_events(detected_at DESC, event_id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_warning_events_source_type
        ON warning_events(source_key, warning_type, detected_at DESC)
    """,
)

MIGRATIONS: tuple[tuple[str, str], ...] = (
    (
        "observation_history",
        "ALTER TABLE observation_history "
        "ADD COLUMN origin TEXT NOT NULL DEFAULT 'live_refresh'",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN import_run_id TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN import_source_url TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN source_station_id TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN station_mapping_status TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN station_mapping_version TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN station_mapping_source_url TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN station_mapping_retrieved_at TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN archive_kind TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN quality_status TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN missing_reason TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN temporal_resolution TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN source_file_sha256 TEXT",
    ),
    (
        "observation_history",
        "ALTER TABLE observation_history ADD COLUMN source_file_last_modified TEXT",
    ),
    (
        "archive_import_runs",
        "ALTER TABLE archive_import_runs "
        "ADD COLUMN observations_deleted INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "archive_import_runs",
        "ALTER TABLE archive_import_runs "
        "ADD COLUMN duplicate_rows INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "warning_events",
        "ALTER TABLE warning_events ADD COLUMN snapshot_id INTEGER",
    ),
)


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


_ENGINE_CONNECTIONS: dict[int, sqlite3.Connection] = {}
_ENGINE_CONNECTIONS_LOCK = RLock()


def get_engine() -> sqlite3.Connection:
    """Return one SQLite connection per worker thread.

    FastAPI runs synchronous endpoints in a thread pool. Sharing one cached
    connection between those threads can overlap SQLite API calls and raise
    ``InterfaceError`` even with ``check_same_thread=False``. Thread-affine
    connections share the same database file without sharing connection state.
    """
    thread_id = get_ident()
    with _ENGINE_CONNECTIONS_LOCK:
        existing = _ENGINE_CONNECTIONS.get(thread_id)
        if existing is not None:
            return existing

        settings = get_settings()
        path = database_path_from_url(settings.database_url)
        if path != Path(":memory:"):
            path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(path), check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _ENGINE_CONNECTIONS[thread_id] = connection
        return connection


def init_db() -> None:
    connection = get_engine()
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in SCHEMA_SQL.split(";"):
            if statement.strip():
                connection.execute(statement)
        for table_name, statement in MIGRATIONS:
            existing_columns = {
                row["name"]
                for row in connection.execute(f"PRAGMA table_info({table_name})")
            }
            column_name = statement.rsplit("ADD COLUMN ", maxsplit=1)[1].split()[0]
            if column_name not in existing_columns:
                connection.execute(statement)
        _migrate_observation_history_origin_key(connection)
        for statement in POST_MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _migrate_observation_history_origin_key(connection: sqlite3.Connection) -> None:
    """Include origin in the history key so live and archive rows cannot overwrite."""
    old_key = ("station_id", "metric", "observed_at")
    unique_indexes = [
        row
        for row in connection.execute("PRAGMA index_list(observation_history)")
        if row["unique"]
    ]
    has_old_key = any(
        tuple(
            column["name"]
            for column in connection.execute(f"PRAGMA index_info({index['name']})")
        )
        == old_key
        for index in unique_indexes
    )
    if not has_old_key:
        return

    columns = (
        "id, station_id, station_name, source_key, station_type, metric, value, "
        "unit, observed_at, retrieved_at, missing, raw_field, origin, import_run_id, "
        "import_source_url, source_station_id, station_mapping_status, "
        "station_mapping_version, station_mapping_source_url, "
        "station_mapping_retrieved_at, archive_kind, quality_status, "
        "missing_reason, temporal_resolution, source_file_sha256, "
        "source_file_last_modified, created_at"
    )
    connection.execute(
        """
            CREATE TABLE observation_history_new (
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
                origin TEXT NOT NULL DEFAULT 'live_refresh',
                import_run_id TEXT,
                import_source_url TEXT,
                source_station_id TEXT,
                station_mapping_status TEXT,
                station_mapping_version TEXT,
                station_mapping_source_url TEXT,
                station_mapping_retrieved_at TEXT,
                archive_kind TEXT,
                quality_status TEXT,
                missing_reason TEXT,
                temporal_resolution TEXT,
                source_file_sha256 TEXT,
                source_file_last_modified TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                UNIQUE(station_id, metric, observed_at, origin)
            )
        """
    )
    connection.execute(
        f"INSERT INTO observation_history_new ({columns}) "
        f"SELECT {columns} FROM observation_history"
    )
    connection.execute("DROP TABLE observation_history")
    connection.execute(
        "ALTER TABLE observation_history_new RENAME TO observation_history"
    )


def reset_engine_cache() -> None:
    with _ENGINE_CONNECTIONS_LOCK:
        connections = list(_ENGINE_CONNECTIONS.values())
        _ENGINE_CONNECTIONS.clear()
    for connection in connections:
        connection.close()
