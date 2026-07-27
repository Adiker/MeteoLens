"""Persist and query prospective IMGW warning history.

The current IMGW JSON endpoints expose a changing set, not an authoritative
change log. This module therefore records exact snapshots and field diffs while
keeping source absence and incomplete identity explicitly ambiguous.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

from app.db.engine import get_engine, init_db
from app.normalization.models import Warning

HistoryCompleteness = Literal["complete", "partial"]


@dataclass(frozen=True)
class WarningSnapshotResult:
    source_key: str
    snapshot_id: int
    completeness: HistoryCompleteness
    histories_seen: int
    versions_created: int
    events_created: int
    event_kind_counts: dict[str, int]
    exact_duplicates: int
    conflicting_duplicates: int


def persist_warning_snapshot(
    records: list[Warning],
    *,
    source_key: str,
    retrieved_at: datetime,
    parser_warnings: list[str],
) -> WarningSnapshotResult:
    """Persist one source refresh atomically without inferring from partial data."""
    if source_key not in {"warningsmeteo", "warningshydro"}:
        raise ValueError(f"Unsupported warning history source: {source_key}")
    if any(record.source_key != source_key for record in records):
        raise ValueError("Warning snapshot contains a record from another source.")

    init_db()
    connection = get_engine()
    retrieved_iso = _iso(retrieved_at)
    prepared = [_prepare_warning(record) for record in records]
    grouped: dict[str, list[_PreparedWarning]] = {}
    for item in prepared:
        grouped.setdefault(item.identity_key, []).append(item)

    exact_duplicates = sum(
        len(items) - len({item.content_hash for item in items})
        for items in grouped.values()
    )
    conflict_groups = {
        key: items
        for key, items in grouped.items()
        if len({item.content_hash for item in items}) > 1
    }
    conflicting_duplicates = sum(len(items) for items in conflict_groups.values())
    completeness: HistoryCompleteness = (
        "partial" if parser_warnings or conflict_groups else "complete"
    )
    snapshot_hash = _hash_json(
        {
            "source_key": source_key,
            "completeness": completeness,
            "members": sorted(
                (item.identity_key, item.content_hash)
                for items in grouped.values()
                for item in _unique_content(items)
            ),
        }
    )

    versions_created = 0
    events_created = 0
    event_kind_counts: dict[str, int] = {}
    present_history_ids: set[str] = set()
    try:
        connection.execute("BEGIN IMMEDIATE")
        previous_snapshot = connection.execute(
            """
            SELECT *
            FROM warning_snapshots
            WHERE source_key = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (source_key,),
        ).fetchone()
        snapshot_id = _upsert_snapshot(
            connection,
            source_key=source_key,
            snapshot_hash=snapshot_hash,
            completeness=completeness,
            retrieved_at=retrieved_iso,
            parser_warnings=parser_warnings,
            exact_duplicates=exact_duplicates,
            conflicting_duplicates=conflicting_duplicates,
            previous=previous_snapshot,
        )

        for items in grouped.values():
            unique_items = _unique_content(items)
            representative = unique_items[0]
            history, created_history, reappeared = _resolve_history(
                connection,
                representative,
                retrieved_at=retrieved_iso,
            )
            history_id = str(history["history_id"])
            present_history_ids.add(history_id)

            if len(unique_items) > 1:
                conflict_version_ids: list[str] = []
                for item in unique_items:
                    version_id, created = _upsert_version(
                        connection,
                        history_id,
                        item,
                        retrieved_at=retrieved_iso,
                    )
                    conflict_version_ids.append(version_id)
                    versions_created += int(created)
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO warning_snapshot_members (
                            snapshot_id, history_id, version_id, duplicate_status
                        ) VALUES (?, ?, ?, 'conflict')
                        """,
                        (snapshot_id, history_id, version_id),
                    )
                events_created += _insert_event(
                    connection,
                    history_id=history_id,
                    source_key=source_key,
                    warning_type=representative.warning.warning_type,
                    detected_at=retrieved_iso,
                    effective_at=None,
                    change_kinds=["duplicate_conflict"],
                    changed_fields=[],
                    classification_basis="source_conflict",
                    confidence="ambiguous",
                    from_version_id=history["current_version_id"],
                    to_version_id=conflict_version_ids[0],
                    snapshot_id=snapshot_id,
                    event_kind_counts=event_kind_counts,
                )
                connection.execute(
                    """
                    UPDATE warning_histories
                    SET status = 'ambiguous',
                        last_observed_at = ?,
                        absent_complete_snapshots = 0
                    WHERE history_id = ?
                    """,
                    (retrieved_iso, history_id),
                )
                continue

            item = unique_items[0]
            version_id, created_version = _upsert_version(
                connection,
                history_id,
                item,
                retrieved_at=retrieved_iso,
            )
            versions_created += int(created_version)
            connection.execute(
                """
                INSERT OR IGNORE INTO warning_snapshot_members (
                    snapshot_id, history_id, version_id, duplicate_status
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    history_id,
                    version_id,
                    "exact_duplicate" if len(items) > 1 else "unique",
                ),
            )

            previous_version_id = history["current_version_id"]
            current_signals = _structured_source_signals(item.warning.raw)
            explicit_kinds: list[str] = []
            if created_history:
                kinds, basis, confidence = _appearance_event(
                    item.warning,
                    previous_snapshot=previous_snapshot,
                    retrieved_at=retrieved_at,
                )
                explicit_kinds = [
                    kind
                    for kind in ("cancelled", "correction")
                    if kind in current_signals
                ]
                kinds.extend(explicit_kinds)
                if explicit_kinds:
                    basis = f"{basis}+explicit_source_signal"
                events_created += _insert_event(
                    connection,
                    history_id=history_id,
                    source_key=source_key,
                    warning_type=item.warning.warning_type,
                    detected_at=retrieved_iso,
                    effective_at=_iso_or_none(item.warning.published_at),
                    change_kinds=kinds,
                    changed_fields=[],
                    classification_basis=basis,
                    confidence=confidence,
                    from_version_id=None,
                    to_version_id=version_id,
                    snapshot_id=snapshot_id,
                    event_kind_counts=event_kind_counts,
                )
            elif reappeared:
                reappearance_kinds = [
                    "reappeared",
                    *(
                        kind
                        for kind in ("cancelled", "correction")
                        if kind in current_signals
                    ),
                ]
                events_created += _insert_event(
                    connection,
                    history_id=history_id,
                    source_key=source_key,
                    warning_type=item.warning.warning_type,
                    detected_at=retrieved_iso,
                    effective_at=retrieved_iso,
                    change_kinds=reappearance_kinds,
                    changed_fields=[],
                    classification_basis="source_presence",
                    confidence="ambiguous",
                    from_version_id=previous_version_id,
                    to_version_id=version_id,
                    snapshot_id=snapshot_id,
                    event_kind_counts=event_kind_counts,
                )
            elif previous_version_id is None:
                events_created += _insert_event(
                    connection,
                    history_id=history_id,
                    source_key=source_key,
                    warning_type=item.warning.warning_type,
                    detected_at=retrieved_iso,
                    effective_at=retrieved_iso,
                    change_kinds=["appeared_in_source"],
                    changed_fields=[],
                    classification_basis="source_conflict_resolved",
                    confidence="ambiguous",
                    from_version_id=None,
                    to_version_id=version_id,
                    snapshot_id=snapshot_id,
                    event_kind_counts=event_kind_counts,
                )

            if previous_version_id and previous_version_id != version_id:
                previous_payload = _version_payload(connection, previous_version_id)
                changed_fields = _changed_fields(previous_payload, item.payload)
                kinds = _change_kinds(previous_payload, item.payload)
                explicit_kinds = _explicit_source_change_kinds(
                    previous_payload.get("raw", {}),
                    item.warning.raw,
                )
                kinds.extend(kind for kind in explicit_kinds if kind not in kinds)
                events_created += _insert_event(
                    connection,
                    history_id=history_id,
                    source_key=source_key,
                    warning_type=item.warning.warning_type,
                    detected_at=retrieved_iso,
                    effective_at=_iso_or_none(item.warning.published_at) or retrieved_iso,
                    change_kinds=kinds,
                    changed_fields=changed_fields,
                    classification_basis=(
                        "explicit_source_signal" if explicit_kinds else "field_diff"
                    ),
                    confidence="confirmed" if explicit_kinds else "derived",
                    from_version_id=previous_version_id,
                    to_version_id=version_id,
                    snapshot_id=snapshot_id,
                    event_kind_counts=event_kind_counts,
                )

            status = (
                "cancelled"
                if "cancelled" in current_signals
                else _present_status(item.warning, retrieved_at)
            )
            connection.execute(
                """
                UPDATE warning_histories
                SET current_version_id = ?,
                    status = ?,
                    last_observed_at = ?,
                    absent_complete_snapshots = 0,
                    identity_status = CASE
                        WHEN identity_status = 'ambiguous' THEN identity_status
                        ELSE ?
                    END
                WHERE history_id = ?
                """,
                (
                    version_id,
                    status,
                    retrieved_iso,
                    item.identity_status,
                    history_id,
                ),
            )

        if completeness == "complete":
            events_created += _process_absences(
                connection,
                source_key=source_key,
                present_history_ids=present_history_ids,
                detected_at=retrieved_iso,
                snapshot_id=snapshot_id,
                event_kind_counts=event_kind_counts,
            )
        events_created += _process_expiries(
            connection,
            source_key=source_key,
            detected_at=retrieved_at,
            snapshot_id=snapshot_id,
            event_kind_counts=event_kind_counts,
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return WarningSnapshotResult(
        source_key=source_key,
        snapshot_id=snapshot_id,
        completeness=completeness,
        histories_seen=len(present_history_ids),
        versions_created=versions_created,
        events_created=events_created,
        event_kind_counts=event_kind_counts,
        exact_duplicates=exact_duplicates,
        conflicting_duplicates=conflicting_duplicates,
    )


def warning_history_link(warning: Warning) -> dict[str, Any] | None:
    """Return the latest persisted history link for a current warning."""
    prepared = _prepare_warning(warning)
    try:
        row = get_engine().execute(
            """
            SELECT history_id, history_started_at, identity_status
            FROM warning_histories
            WHERE identity_key = ?
            ORDER BY generation DESC
            LIMIT 1
            """,
            (prepared.identity_key,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    return {
        "history_id": row["history_id"],
        "history_available": True,
        "history_started_at": row["history_started_at"],
        "history_identity_status": row["identity_status"],
    }


def list_warning_events(
    *,
    warning_type: str | None = None,
    level: int | None = None,
    phenomenon: str | None = None,
    office: str | None = None,
    area: str | None = None,
    change_kind: str | None = None,
    detected_from: datetime | None = None,
    detected_to: datetime | None = None,
    cursor: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    init_db()
    conditions: list[str] = []
    params: list[Any] = []
    if warning_type:
        conditions.append("e.warning_type = ?")
        params.append(warning_type)
    if level is not None:
        conditions.append("v.level = ?")
        params.append(level)
    if phenomenon:
        conditions.append("LOWER(v.event_name) LIKE ?")
        params.append(f"%{phenomenon.casefold()}%")
    if office:
        conditions.append("LOWER(COALESCE(v.office, '')) LIKE ?")
        params.append(f"%{office.casefold()}%")
    if area:
        conditions.append(
            """
            EXISTS (
                SELECT 1 FROM warning_version_areas a
                WHERE a.version_id = COALESCE(e.to_version_id, e.from_version_id)
                  AND a.code = ?
            )
            """
        )
        params.append(area)
    if change_kind:
        conditions.append("e.change_kinds LIKE ?")
        params.append(f'%"{change_kind}"%')
    if detected_from:
        conditions.append("e.detected_at >= ?")
        params.append(_iso(detected_from))
    if detected_to:
        conditions.append("e.detected_at <= ?")
        params.append(_iso(detected_to))
    if cursor:
        cursor_time, cursor_id = _decode_cursor(cursor)
        conditions.append("(e.detected_at < ? OR (e.detected_at = ? AND e.event_id < ?))")
        params.extend((cursor_time, cursor_time, cursor_id))

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = get_engine().execute(
        f"""
        SELECT e.*,
               h.source_id, h.office AS identity_office, h.identity_status,
               h.status AS history_status, h.history_started_at,
               v.event_name, v.level, v.probability, v.valid_from, v.valid_to,
               v.published_at, v.office, v.missing_fields, v.normalized_payload,
               v.raw_payload, v.source_metadata,
               s.completeness AS snapshot_completeness,
               s.first_retrieved_at AS snapshot_first_retrieved_at,
               s.last_retrieved_at AS snapshot_last_retrieved_at,
               s.seen_count AS snapshot_seen_count,
               s.parser_warnings AS snapshot_parser_warnings,
               s.exact_duplicate_count AS snapshot_exact_duplicate_count,
               s.conflicting_duplicate_count AS snapshot_conflicting_duplicate_count
        FROM warning_events e
        JOIN warning_histories h ON h.history_id = e.history_id
        LEFT JOIN warning_versions v
          ON v.version_id = COALESCE(e.to_version_id, e.from_version_id)
        LEFT JOIN warning_snapshots s ON s.id = e.snapshot_id
        {where}
        ORDER BY e.detected_at DESC, e.event_id DESC
        LIMIT ?
        """,
        (*params, limit + 1),
    ).fetchall()
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = (
        _encode_cursor(page[-1]["detected_at"], page[-1]["event_id"])
        if has_more and page
        else None
    )
    return {
        "events": [_event_payload(row) for row in page],
        "next_cursor": next_cursor,
        "history_started_at": get_engine()
        .execute("SELECT MIN(history_started_at) FROM warning_histories")
        .fetchone()[0],
    }


def get_warning_history(history_id: str) -> dict[str, Any] | None:
    init_db()
    connection = get_engine()
    history = connection.execute(
        "SELECT * FROM warning_histories WHERE history_id = ?",
        (history_id,),
    ).fetchone()
    if history is None:
        return None
    version_rows = connection.execute(
        """
        SELECT *
        FROM warning_versions
        WHERE history_id = ?
        ORDER BY first_seen_at, version_id
        """,
        (history_id,),
    ).fetchall()
    event_rows = connection.execute(
        """
        SELECT e.*,
               h.source_id, h.office AS identity_office, h.identity_status,
               h.status AS history_status, h.history_started_at,
               v.event_name, v.level, v.probability, v.valid_from, v.valid_to,
               v.published_at, v.office, v.missing_fields, v.normalized_payload,
               v.raw_payload, v.source_metadata,
               s.completeness AS snapshot_completeness,
               s.first_retrieved_at AS snapshot_first_retrieved_at,
               s.last_retrieved_at AS snapshot_last_retrieved_at,
               s.seen_count AS snapshot_seen_count,
               s.parser_warnings AS snapshot_parser_warnings,
               s.exact_duplicate_count AS snapshot_exact_duplicate_count,
               s.conflicting_duplicate_count AS snapshot_conflicting_duplicate_count
        FROM warning_events e
        JOIN warning_histories h ON h.history_id = e.history_id
        LEFT JOIN warning_versions v
          ON v.version_id = COALESCE(e.to_version_id, e.from_version_id)
        LEFT JOIN warning_snapshots s ON s.id = e.snapshot_id
        WHERE e.history_id = ?
        ORDER BY e.detected_at, e.event_id
        """,
        (history_id,),
    ).fetchall()
    snapshot_rows = connection.execute(
        """
        SELECT DISTINCT s.*
        FROM warning_snapshots s
        JOIN warning_snapshot_members m ON m.snapshot_id = s.id
        WHERE m.history_id = ?
        ORDER BY s.first_retrieved_at, s.id
        """,
        (history_id,),
    ).fetchall()
    return {
        "history_id": history["history_id"],
        "source_key": history["source_key"],
        "source_id": history["source_id"],
        "warning_type": history["warning_type"],
        "office": history["office"],
        "identity_status": history["identity_status"],
        "status": history["status"],
        "first_observed_at": history["first_observed_at"],
        "last_observed_at": history["last_observed_at"],
        "history_started_at": history["history_started_at"],
        "current_version_id": history["current_version_id"],
        "versions": [_version_row_payload(row) for row in version_rows],
        "snapshots": [_snapshot_payload(row) for row in snapshot_rows],
        "events": [_event_payload(row) for row in event_rows],
    }


def prune_warning_histories(
    *,
    before: date,
    confirm: bool = False,
    source_key: str | None = None,
) -> dict[str, Any]:
    """Dry-run-first deletion of complete closed histories."""
    init_db()
    connection = get_engine()
    cutoff = datetime.combine(before, datetime.min.time(), tzinfo=UTC).isoformat()
    conditions = ["status IN ('removed', 'expired', 'cancelled')", "last_observed_at < ?"]
    params: list[Any] = [cutoff]
    if source_key:
        conditions.append("source_key = ?")
        params.append(source_key)
    rows = connection.execute(
        f"SELECT history_id FROM warning_histories WHERE {' AND '.join(conditions)}",
        params,
    ).fetchall()
    history_ids = [row["history_id"] for row in rows]
    counts = _prune_counts(connection, history_ids)
    result = {
        "before": before.isoformat(),
        "source_key": source_key,
        "confirmed": confirm,
        **counts,
    }
    if not confirm or not history_ids:
        return result

    placeholders = ",".join("?" for _ in history_ids)
    try:
        connection.execute("BEGIN IMMEDIATE")
        version_ids = [
            row["version_id"]
            for row in connection.execute(
                f"SELECT version_id FROM warning_versions WHERE history_id IN ({placeholders})",
                history_ids,
            )
        ]
        if version_ids:
            version_placeholders = ",".join("?" for _ in version_ids)
            connection.execute(
                f"DELETE FROM warning_version_areas WHERE version_id IN ({version_placeholders})",
                version_ids,
            )
        connection.execute(
            f"DELETE FROM warning_snapshot_members WHERE history_id IN ({placeholders})",
            history_ids,
        )
        connection.execute(
            f"DELETE FROM warning_events WHERE history_id IN ({placeholders})",
            history_ids,
        )
        connection.execute(
            f"DELETE FROM warning_versions WHERE history_id IN ({placeholders})",
            history_ids,
        )
        connection.execute(
            f"DELETE FROM warning_histories WHERE history_id IN ({placeholders})",
            history_ids,
        )
        connection.execute(
            """
            DELETE FROM warning_snapshots
            WHERE NOT EXISTS (
                SELECT 1 FROM warning_snapshot_members m
                WHERE m.snapshot_id = warning_snapshots.id
            )
              AND NOT EXISTS (
                SELECT 1 FROM warning_events e
                WHERE e.snapshot_id = warning_snapshots.id
            )
            """
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return result


@dataclass(frozen=True)
class _PreparedWarning:
    warning: Warning
    identity_key: str
    identity_status: str
    content_hash: str
    payload: dict[str, Any]


def _prepare_warning(warning: Warning) -> _PreparedWarning:
    payload = warning.model_dump(mode="json")
    hash_payload = json.loads(json.dumps(payload))
    hash_payload.get("source", {}).pop("retrieved_at", None)
    content_hash = _hash_json(hash_payload)
    missing_source_id = not warning.source_id or (
        warning.source_key == "warningshydro" and "numer" in warning.missing_fields
    )
    if warning.source_key == "warningsmeteo" and not missing_source_id:
        identity_key = f"v1:{warning.source_key}:{warning.source_id}"
        identity_status = "exact"
    elif (
        warning.source_key == "warningshydro"
        and not missing_source_id
        and warning.office
    ):
        identity_key = f"v1:{warning.source_key}:{warning.source_id}:{warning.office}"
        identity_status = "exact"
    else:
        identity_key = f"v1:{warning.source_key}:ambiguous:{content_hash}"
        identity_status = "ambiguous"
    return _PreparedWarning(
        warning=warning,
        identity_key=identity_key,
        identity_status=identity_status,
        content_hash=content_hash,
        payload=payload,
    )


def _resolve_history(
    connection: sqlite3.Connection,
    item: _PreparedWarning,
    *,
    retrieved_at: str,
) -> tuple[sqlite3.Row, bool, bool]:
    latest = connection.execute(
        """
        SELECT *
        FROM warning_histories
        WHERE identity_key = ?
        ORDER BY generation DESC
        LIMIT 1
        """,
        (item.identity_key,),
    ).fetchone()
    if latest is not None and latest["status"] in {"removed", "expired", "cancelled"}:
        if _proves_new_generation(connection, latest, item.warning):
            latest = None
        elif latest["status"] == "removed":
            return latest, False, True
        elif latest["status"] == "expired":
            if _present_status(item.warning, datetime.fromisoformat(retrieved_at)) == "expired":
                return latest, False, False
            return latest, False, True
        elif "cancelled" not in _structured_source_signals(item.warning.raw):
            return latest, False, True
        else:
            return latest, False, False
    if latest is not None:
        return latest, False, False

    generation_row = connection.execute(
        "SELECT MAX(generation) AS generation FROM warning_histories WHERE identity_key = ?",
        (item.identity_key,),
    ).fetchone()
    generation = int(generation_row["generation"] or 0) + 1
    history_id = f"wh:{_hash_text(f'{item.identity_key}:{generation}')[:24]}"
    connection.execute(
        """
        INSERT INTO warning_histories (
            history_id, identity_key, generation, identity_status, source_key,
            source_id, warning_type, office, status, first_observed_at,
            last_observed_at, history_started_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
        """,
        (
            history_id,
            item.identity_key,
            generation,
            item.identity_status,
            item.warning.source_key,
            item.warning.source_id or None,
            item.warning.warning_type,
            item.warning.office,
            retrieved_at,
            retrieved_at,
            retrieved_at,
        ),
    )
    row = connection.execute(
        "SELECT * FROM warning_histories WHERE history_id = ?",
        (history_id,),
    ).fetchone()
    assert row is not None
    return row, True, False


def _proves_new_generation(
    connection: sqlite3.Connection,
    history: sqlite3.Row,
    warning: Warning,
) -> bool:
    if warning.published_at is None or history["current_version_id"] is None:
        return False
    if history["status"] == "cancelled":
        if "cancelled" in _structured_source_signals(warning.raw):
            return False
        cancellation = connection.execute(
            """
            SELECT detected_at
            FROM warning_events
            WHERE history_id = ? AND change_kinds LIKE '%"cancelled"%'
            ORDER BY detected_at DESC
            LIMIT 1
            """,
            (history["history_id"],),
        ).fetchone()
        if cancellation is not None:
            return warning.published_at > datetime.fromisoformat(cancellation["detected_at"])
    previous = connection.execute(
        "SELECT valid_to FROM warning_versions WHERE version_id = ?",
        (history["current_version_id"],),
    ).fetchone()
    if previous is None or previous["valid_to"] is None:
        return False
    try:
        previous_valid_to = datetime.fromisoformat(previous["valid_to"])
    except ValueError:
        return False
    return warning.published_at > previous_valid_to


def _upsert_snapshot(
    connection: sqlite3.Connection,
    *,
    source_key: str,
    snapshot_hash: str,
    completeness: str,
    retrieved_at: str,
    parser_warnings: list[str],
    exact_duplicates: int,
    conflicting_duplicates: int,
    previous: sqlite3.Row | None,
) -> int:
    if (
        previous is not None
        and previous["snapshot_hash"] == snapshot_hash
        and previous["completeness"] == completeness
    ):
        connection.execute(
            """
            UPDATE warning_snapshots
            SET last_retrieved_at = ?, seen_count = seen_count + 1,
                parser_warnings = ?, exact_duplicate_count = ?,
                conflicting_duplicate_count = ?
            WHERE id = ?
            """,
            (
                retrieved_at,
                _json(parser_warnings),
                exact_duplicates,
                conflicting_duplicates,
                previous["id"],
            ),
        )
        return int(previous["id"])
    cursor = connection.execute(
        """
        INSERT INTO warning_snapshots (
            source_key, snapshot_hash, completeness, first_retrieved_at,
            last_retrieved_at, parser_warnings, exact_duplicate_count,
            conflicting_duplicate_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_key,
            snapshot_hash,
            completeness,
            retrieved_at,
            retrieved_at,
            _json(parser_warnings),
            exact_duplicates,
            conflicting_duplicates,
        ),
    )
    return int(cursor.lastrowid)


def _upsert_version(
    connection: sqlite3.Connection,
    history_id: str,
    item: _PreparedWarning,
    *,
    retrieved_at: str,
) -> tuple[str, bool]:
    existing = connection.execute(
        """
        SELECT version_id FROM warning_versions
        WHERE history_id = ? AND content_hash = ?
        """,
        (history_id, item.content_hash),
    ).fetchone()
    if existing is not None:
        connection.execute(
            "UPDATE warning_versions SET last_seen_at = ? WHERE version_id = ?",
            (retrieved_at, existing["version_id"]),
        )
        return str(existing["version_id"]), False

    version_id = f"wv:{_hash_text(f'{history_id}:{item.content_hash}')[:24]}"
    source_metadata = item.warning.source.model_dump(mode="json")
    connection.execute(
        """
        INSERT INTO warning_versions (
            version_id, history_id, content_hash, first_seen_at, last_seen_at,
            event_name, level, probability, valid_from, valid_to, published_at,
            office, missing_fields, normalized_payload, raw_payload, source_metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            history_id,
            item.content_hash,
            retrieved_at,
            retrieved_at,
            item.warning.event,
            item.warning.level,
            item.warning.probability,
            _iso_or_none(item.warning.valid_from),
            _iso_or_none(item.warning.valid_to),
            _iso_or_none(item.warning.published_at),
            item.warning.office,
            _json(item.warning.missing_fields),
            _json(item.payload),
            _json(item.warning.raw),
            _json(source_metadata),
        ),
    )
    for area in item.warning.areas:
        connection.execute(
            """
            INSERT OR IGNORE INTO warning_version_areas (
                version_id, area_type, code, label, region
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (version_id, area.area_type, area.code, area.label, area.region),
        )
    return version_id, True


def _appearance_event(
    warning: Warning,
    *,
    previous_snapshot: sqlite3.Row | None,
    retrieved_at: datetime,
) -> tuple[list[str], str, str]:
    if previous_snapshot is None:
        return ["first_observed"], "local_baseline", "confirmed"
    if warning.published_at is not None:
        previous_time = datetime.fromisoformat(previous_snapshot["last_retrieved_at"])
        if previous_time <= warning.published_at <= retrieved_at:
            return ["created"], "source_timestamp", "confirmed"
    return ["appeared_in_source"], "source_presence", "ambiguous"


def _process_absences(
    connection: sqlite3.Connection,
    *,
    source_key: str,
    present_history_ids: set[str],
    detected_at: str,
    snapshot_id: int,
    event_kind_counts: dict[str, int],
) -> int:
    conditions = [
        "source_key = ?",
        "status IN ('active', 'expired', 'ambiguous')",
    ]
    params: list[Any] = [source_key]
    if present_history_ids:
        placeholders = ",".join("?" for _ in present_history_ids)
        conditions.append(f"history_id NOT IN ({placeholders})")
        params.extend(sorted(present_history_ids))
    rows = connection.execute(
        f"SELECT * FROM warning_histories WHERE {' AND '.join(conditions)}",
        params,
    ).fetchall()
    events = 0
    for history in rows:
        absent_count = int(history["absent_complete_snapshots"]) + 1
        connection.execute(
            """
            UPDATE warning_histories
            SET absent_complete_snapshots = ?
            WHERE history_id = ?
            """,
            (absent_count, history["history_id"]),
        )
        if absent_count < 2:
            continue
        events += _insert_event(
            connection,
            history_id=history["history_id"],
            source_key=history["source_key"],
            warning_type=history["warning_type"],
            detected_at=detected_at,
            effective_at=detected_at,
            change_kinds=["removed_from_source"],
            changed_fields=[],
            classification_basis="source_presence",
            confidence="ambiguous",
            from_version_id=history["current_version_id"],
            to_version_id=history["current_version_id"],
            snapshot_id=snapshot_id,
            event_kind_counts=event_kind_counts,
        )
        connection.execute(
            "UPDATE warning_histories SET status = 'removed' WHERE history_id = ?",
            (history["history_id"],),
        )
    return events


def _process_expiries(
    connection: sqlite3.Connection,
    *,
    source_key: str,
    detected_at: datetime,
    snapshot_id: int,
    event_kind_counts: dict[str, int],
) -> int:
    rows = connection.execute(
        """
        SELECT h.*, v.valid_to
        FROM warning_histories h
        JOIN warning_versions v ON v.version_id = h.current_version_id
        WHERE h.source_key = ?
          AND h.status IN ('active', 'ambiguous', 'expired')
          AND v.valid_to IS NOT NULL
          AND v.valid_to <= ?
        """,
        (source_key, _iso(detected_at)),
    ).fetchall()
    events = 0
    for history in rows:
        try:
            valid_to = datetime.fromisoformat(history["valid_to"])
        except ValueError:
            continue
        if valid_to.year >= 9999:
            continue
        exists = connection.execute(
            """
            SELECT 1 FROM warning_events
            WHERE history_id = ? AND change_kinds LIKE '%"expired"%'
              AND effective_at = ?
            """,
            (history["history_id"], history["valid_to"]),
        ).fetchone()
        if exists is not None:
            continue
        events += _insert_event(
            connection,
            history_id=history["history_id"],
            source_key=history["source_key"],
            warning_type=history["warning_type"],
            detected_at=_iso(detected_at),
            effective_at=history["valid_to"],
            change_kinds=["expired"],
            changed_fields=["valid_to"],
            classification_basis="time_rule",
            confidence="derived",
            from_version_id=history["current_version_id"],
            to_version_id=history["current_version_id"],
            snapshot_id=snapshot_id,
            event_kind_counts=event_kind_counts,
        )
        connection.execute(
            "UPDATE warning_histories SET status = 'expired' WHERE history_id = ?",
            (history["history_id"],),
        )
    return events


def _insert_event(
    connection: sqlite3.Connection,
    *,
    history_id: str,
    source_key: str,
    warning_type: str,
    detected_at: str,
    effective_at: str | None,
    change_kinds: list[str],
    changed_fields: list[str],
    classification_basis: str,
    confidence: str,
    from_version_id: str | None,
    to_version_id: str | None,
    snapshot_id: int,
    event_kind_counts: dict[str, int],
) -> int:
    event_id = f"we:{_hash_json({
        'history_id': history_id,
        'detected_at': detected_at,
        'effective_at': effective_at,
        'change_kinds': change_kinds,
        'from': from_version_id,
        'to': to_version_id,
    })[:24]}"
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO warning_events (
            event_id, history_id, source_key, warning_type, detected_at,
            effective_at, change_kinds, changed_fields, classification_basis,
            confidence, from_version_id, to_version_id, snapshot_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            history_id,
            source_key,
            warning_type,
            detected_at,
            effective_at,
            _json(change_kinds),
            _json(changed_fields),
            classification_basis,
            confidence,
            from_version_id,
            to_version_id,
            snapshot_id,
        ),
    )
    created = int(cursor.rowcount > 0)
    if created:
        for change_kind in change_kinds:
            event_kind_counts[change_kind] = event_kind_counts.get(change_kind, 0) + 1
    return created


def _version_payload(connection: sqlite3.Connection, version_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT normalized_payload FROM warning_versions WHERE version_id = ?",
        (version_id,),
    ).fetchone()
    return json.loads(row["normalized_payload"]) if row else {}


def _changed_fields(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    fields = (
        "event",
        "level",
        "probability",
        "valid_from",
        "valid_to",
        "published_at",
        "office",
        "content",
        "comment",
        "areas",
        "missing_fields",
        "raw",
    )
    return [field for field in fields if previous.get(field) != current.get(field)]


def _change_kinds(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    kinds = ["updated"]
    old_level = previous.get("level")
    new_level = current.get("level")
    if old_level in {1, 2, 3} and new_level in {1, 2, 3}:
        if new_level > old_level:
            kinds.append("escalated")
        elif new_level < old_level:
            kinds.append("downgraded")
    if _datetime_later(current.get("valid_to"), previous.get("valid_to")):
        kinds.append("extended")
    old_areas = {
        (area.get("area_type"), area.get("code"))
        for area in previous.get("areas", [])
    }
    new_areas = {
        (area.get("area_type"), area.get("code"))
        for area in current.get("areas", [])
    }
    if old_areas and old_areas < new_areas and "extended" not in kinds:
        kinds.append("extended")
    return kinds


def _explicit_source_change_kinds(
    previous_raw: dict[str, object],
    current_raw: dict[str, object],
) -> list[str]:
    """Recognize only structured source markers, never free-text descriptions."""
    previous = _structured_source_signals(previous_raw)
    current = _structured_source_signals(current_raw)
    return [kind for kind in ("cancelled", "correction") if kind in current - previous]


def _structured_source_signals(raw: dict[str, object]) -> set[str]:
    kinds: set[str] = set()
    normalized = {
        str(key).casefold(): str(value).strip().casefold()
        for key, value in raw.items()
        if value is not None
    }
    status = normalized.get("status") or normalized.get("stan")
    change_type = normalized.get("typ_zmiany") or normalized.get("change_type")
    cancelled_flag = raw.get("odwolane") is True or raw.get("odwołane") is True
    correction_flag = raw.get("korekta") is True or raw.get("correction") is True
    if cancelled_flag or status in {"cancelled", "canceled", "odwolane", "odwołane"}:
        kinds.add("cancelled")
    if correction_flag or change_type in {"correction", "korekta"}:
        kinds.add("correction")
    return kinds


def _present_status(warning: Warning, retrieved_at: datetime) -> str:
    if warning.valid_to and warning.valid_to.year < 9999 and warning.valid_to <= retrieved_at:
        return "expired"
    return "active"


def _datetime_later(current: Any, previous: Any) -> bool:
    if not current or not previous:
        return False
    try:
        return datetime.fromisoformat(str(current)) > datetime.fromisoformat(str(previous))
    except ValueError:
        return False


def _event_payload(row: sqlite3.Row) -> dict[str, Any]:
    warning = (
        _public_warning_payload(json.loads(row["normalized_payload"]))
        if row["normalized_payload"]
        else None
    )
    source = json.loads(row["source_metadata"]) if row["source_metadata"] else None
    return {
        "event_id": row["event_id"],
        "history_id": row["history_id"],
        "source_key": row["source_key"],
        "source_id": row["source_id"],
        "warning_type": row["warning_type"],
        "detected_at": row["detected_at"],
        "effective_at": row["effective_at"],
        "change_kinds": json.loads(row["change_kinds"]),
        "changed_fields": json.loads(row["changed_fields"]),
        "classification_basis": row["classification_basis"],
        "confidence": row["confidence"],
        "from_version_id": row["from_version_id"],
        "to_version_id": row["to_version_id"],
        "identity_status": row["identity_status"],
        "history_status": row["history_status"],
        "history_started_at": row["history_started_at"],
        "warning": warning,
        "source": source,
        "snapshot": (
            {
                "snapshot_id": row["snapshot_id"],
                "completeness": row["snapshot_completeness"],
                "first_retrieved_at": row["snapshot_first_retrieved_at"],
                "last_retrieved_at": row["snapshot_last_retrieved_at"],
                "seen_count": row["snapshot_seen_count"],
                "parser_warnings": json.loads(row["snapshot_parser_warnings"]),
                "exact_duplicate_count": row["snapshot_exact_duplicate_count"],
                "conflicting_duplicate_count": row[
                    "snapshot_conflicting_duplicate_count"
                ],
            }
            if row["snapshot_completeness"]
            else None
        ),
    }


def _version_row_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = _public_warning_payload(json.loads(row["normalized_payload"]))
    return {
        "version_id": row["version_id"],
        "content_hash": row["content_hash"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "warning": payload,
        "raw": json.loads(row["raw_payload"]),
        "source": json.loads(row["source_metadata"]),
    }


def _public_warning_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Add the compatible derived fields exposed by current warning responses."""
    return {
        **payload,
        "area_codes": [
            area["code"]
            for area in payload.get("areas", [])
            if isinstance(area, dict) and area.get("code")
        ],
        "raw_available": True,
    }


def _snapshot_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "snapshot_id": row["id"],
        "source_key": row["source_key"],
        "completeness": row["completeness"],
        "first_retrieved_at": row["first_retrieved_at"],
        "last_retrieved_at": row["last_retrieved_at"],
        "seen_count": row["seen_count"],
        "parser_warnings": json.loads(row["parser_warnings"]),
        "exact_duplicate_count": row["exact_duplicate_count"],
        "conflicting_duplicate_count": row["conflicting_duplicate_count"],
    }


def _prune_counts(
    connection: sqlite3.Connection,
    history_ids: list[str],
) -> dict[str, int]:
    if not history_ids:
        return {"histories": 0, "versions": 0, "events": 0, "snapshots": 0}
    placeholders = ",".join("?" for _ in history_ids)
    versions = connection.execute(
        f"SELECT COUNT(*) AS count FROM warning_versions WHERE history_id IN ({placeholders})",
        history_ids,
    ).fetchone()["count"]
    events = connection.execute(
        f"SELECT COUNT(*) AS count FROM warning_events WHERE history_id IN ({placeholders})",
        history_ids,
    ).fetchone()["count"]
    snapshots = connection.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM warning_snapshots s
        WHERE (
            EXISTS (
                SELECT 1 FROM warning_snapshot_members selected
                WHERE selected.snapshot_id = s.id
                  AND selected.history_id IN ({placeholders})
            )
            OR EXISTS (
                SELECT 1 FROM warning_events selected_event
                WHERE selected_event.snapshot_id = s.id
                  AND selected_event.history_id IN ({placeholders})
            )
        )
          AND NOT EXISTS (
            SELECT 1 FROM warning_snapshot_members retained
            WHERE retained.snapshot_id = s.id
              AND retained.history_id NOT IN ({placeholders})
        )
          AND NOT EXISTS (
            SELECT 1 FROM warning_events retained_event
            WHERE retained_event.snapshot_id = s.id
              AND retained_event.history_id NOT IN ({placeholders})
        )
        """,
        (*history_ids, *history_ids, *history_ids, *history_ids),
    ).fetchone()["count"]
    return {
        "histories": len(history_ids),
        "versions": int(versions),
        "events": int(events),
        "snapshots": int(snapshots),
    }


def _unique_content(items: list[_PreparedWarning]) -> list[_PreparedWarning]:
    unique: dict[str, _PreparedWarning] = {}
    for item in items:
        unique.setdefault(item.content_hash, item)
    return list(unique.values())


def _encode_cursor(detected_at: str, event_id: str) -> str:
    raw = json.dumps([detected_at, event_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded).decode())
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(isinstance(item, str) for item in value)
        ):
            raise ValueError
        datetime.fromisoformat(value[0])
        if not value[1].startswith("we:"):
            raise ValueError
        return value[0], value[1]
    except (
        binascii.Error,
        UnicodeDecodeError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError("Invalid warning event cursor.") from exc


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _iso_or_none(value: datetime | None) -> str | None:
    return _iso(value) if value is not None else None


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_json(value: Any) -> str:
    return _hash_text(_json(value))


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
