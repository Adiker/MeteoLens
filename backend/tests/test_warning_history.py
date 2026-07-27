import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.services.warning_history as warning_history_service
from app.core.config import Settings
from app.db.engine import get_engine, init_db
from app.main import app
from app.normalization.models import SourceMetadata, Warning, WarningArea
from app.services.warning_history import (
    get_warning_history,
    list_warning_events,
    persist_warning_snapshot,
    prune_warning_histories,
)
from tests.settings_helpers import apply_test_settings


def _prepare(monkeypatch, tmp_path: Path) -> Settings:
    settings = Settings(
        cache_dir=tmp_path / "cache",
        geometry_dir=tmp_path / "geometry",
        database_url=f"sqlite:///{tmp_path / 'history.sqlite3'}",
    )
    apply_test_settings(monkeypatch, settings)
    init_db()
    return settings


def _warning(
    *,
    retrieved_at: datetime,
    source_key: str = "warningsmeteo",
    source_id: str = "meteo-1",
    office: str | None = "CBPM Warszawa",
    event: str = "Burze",
    level: int = 1,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    published_at: datetime | None = None,
    area: str = "1465",
) -> Warning:
    warning_type = "meteo" if source_key == "warningsmeteo" else "hydro"
    return Warning(
        id=f"{source_key}:{source_id}:{published_at or ''}",
        source_id=source_id,
        source_key=source_key,
        warning_type=warning_type,
        event=event,
        level=level,
        probability=80,
        valid_from=valid_from or retrieved_at,
        valid_to=valid_to or retrieved_at + timedelta(hours=6),
        published_at=published_at or retrieved_at,
        office=office,
        content="Prognozowane zjawisko.",
        comment=None,
        areas=[
            WarningArea(
                area_type="teryt" if warning_type == "meteo" else "basin",
                code=area,
                label=area,
            )
        ],
        missing_fields=[],
        source=SourceMetadata(
            source_key=source_key,
            url=f"https://danepubliczne.imgw.pl/api/data/{source_key}",
            retrieved_at=retrieved_at,
        ),
        raw={"id": source_id, "event": event, "level": str(level)},
    )


def test_warning_history_baseline_is_idempotent_and_classifies_changes(
    monkeypatch, tmp_path
) -> None:
    _prepare(monkeypatch, tmp_path)
    first_at = datetime(2026, 7, 27, 10, tzinfo=UTC)
    first = _warning(retrieved_at=first_at)

    baseline = persist_warning_snapshot(
        [first],
        source_key="warningsmeteo",
        retrieved_at=first_at,
        parser_warnings=[],
    )
    repeated_at = first_at + timedelta(minutes=5)
    repeated = first.model_copy(
        update={
            "source": first.source.model_copy(update={"retrieved_at": repeated_at}),
        }
    )
    unchanged = persist_warning_snapshot(
        [repeated],
        source_key="warningsmeteo",
        retrieved_at=repeated_at,
        parser_warnings=[],
    )
    changed_at = repeated_at + timedelta(minutes=5)
    changed = repeated.model_copy(
        update={
            "level": 2,
            "valid_to": first.valid_to + timedelta(hours=2),
            "published_at": changed_at,
            "source": first.source.model_copy(update={"retrieved_at": changed_at}),
            "raw": {"id": "meteo-1", "event": "Burze", "level": "2"},
        }
    )
    update = persist_warning_snapshot(
        [changed],
        source_key="warningsmeteo",
        retrieved_at=changed_at,
        parser_warnings=[],
    )

    events = list_warning_events(limit=20)["events"]
    assert baseline.versions_created == 1
    assert baseline.events_created == 1
    assert unchanged.versions_created == 0
    assert unchanged.events_created == 0
    assert update.versions_created == 1
    assert {"updated", "extended", "escalated"} <= set(events[0]["change_kinds"])
    assert events[-1]["change_kinds"] == ["first_observed"]
    assert events[0]["changed_fields"] == [
        "level",
        "valid_to",
        "published_at",
        "raw",
    ]
    assert update.event_kind_counts == {
        "updated": 1,
        "escalated": 1,
        "extended": 1,
    }

    history = get_warning_history(events[0]["history_id"])
    assert history is not None
    assert len(history["versions"]) == 2
    assert len(history["events"]) == 2


def test_stage24_schema_is_additive_and_idempotent(monkeypatch, tmp_path) -> None:
    _prepare(monkeypatch, tmp_path)
    connection = get_engine()
    connection.execute(
        """
        INSERT INTO observation_history (
            station_id, station_name, source_key, station_type, metric, value,
            unit, observed_at, retrieved_at, missing, raw_field
        ) VALUES (
            'hydro:legacy', 'Legacy', 'hydro', 'hydro', 'water_level', 120,
            'cm', '2026-07-26T10:00:00+00:00', '2026-07-26T10:01:00+00:00',
            0, 'stan_wody'
        )
        """
    )
    for table in (
        "warning_events",
        "warning_snapshot_members",
        "warning_version_areas",
        "warning_versions",
        "warning_snapshots",
        "warning_histories",
    ):
        connection.execute(f"DROP TABLE {table}")
    connection.commit()

    init_db()
    init_db()

    assert (
        connection.execute("SELECT COUNT(*) FROM observation_history").fetchone()[0] == 1
    )
    assert (
        connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type = 'table' AND name LIKE 'warning_%'"
        ).fetchone()[0]
        == 6
    )


def test_snapshot_rolls_back_all_history_rows_on_failure(monkeypatch, tmp_path) -> None:
    _prepare(monkeypatch, tmp_path)
    observed = datetime(2026, 7, 27, 10, tzinfo=UTC)

    def fail_version_write(*args, **kwargs):
        raise RuntimeError("injected version failure")

    monkeypatch.setattr(
        warning_history_service,
        "_upsert_version",
        fail_version_write,
    )
    with pytest.raises(RuntimeError, match="injected version failure"):
        persist_warning_snapshot(
            [_warning(retrieved_at=observed)],
            source_key="warningsmeteo",
            retrieved_at=observed,
            parser_warnings=[],
        )

    counts = get_engine().execute(
        "SELECT "
        "(SELECT COUNT(*) FROM warning_histories), "
        "(SELECT COUNT(*) FROM warning_snapshots), "
        "(SELECT COUNT(*) FROM warning_versions), "
        "(SELECT COUNT(*) FROM warning_events)"
    ).fetchone()
    assert tuple(counts) == (0, 0, 0, 0)


def test_absence_requires_two_complete_snapshots_and_partial_does_not_close(
    monkeypatch, tmp_path
) -> None:
    _prepare(monkeypatch, tmp_path)
    started = datetime(2026, 7, 27, 10, tzinfo=UTC)
    warning = _warning(
        retrieved_at=started,
        valid_to=started + timedelta(days=1),
    )
    persist_warning_snapshot(
        [warning],
        source_key="warningsmeteo",
        retrieved_at=started,
        parser_warnings=[],
    )
    persist_warning_snapshot(
        [],
        source_key="warningsmeteo",
        retrieved_at=started + timedelta(minutes=5),
        parser_warnings=["Meteo warning row 0 is malformed."],
    )
    persist_warning_snapshot(
        [],
        source_key="warningsmeteo",
        retrieved_at=started + timedelta(minutes=10),
        parser_warnings=[],
    )
    before_confirmation = list_warning_events(change_kind="removed_from_source")["events"]
    persist_warning_snapshot(
        [],
        source_key="warningsmeteo",
        retrieved_at=started + timedelta(minutes=15),
        parser_warnings=[],
    )
    after_confirmation = list_warning_events(change_kind="removed_from_source")["events"]

    assert before_confirmation == []
    assert len(after_confirmation) == 1
    assert after_confirmation[0]["confidence"] == "ambiguous"

    reappeared_at = started + timedelta(minutes=20)
    reappeared = warning.model_copy(
        update={
            "source": warning.source.model_copy(update={"retrieved_at": reappeared_at})
        }
    )
    persist_warning_snapshot(
        [reappeared],
        source_key="warningsmeteo",
        retrieved_at=reappeared_at,
        parser_warnings=[],
    )
    assert len(list_warning_events(change_kind="reappeared")["events"]) == 1


def test_appearance_expiry_downgrade_and_explicit_source_signals(
    monkeypatch, tmp_path
) -> None:
    _prepare(monkeypatch, tmp_path)
    started = datetime(2026, 7, 27, 10, tzinfo=UTC)
    baseline = _warning(
        retrieved_at=started,
        source_id="changing",
        level=3,
        valid_to=started + timedelta(hours=2),
    )
    finite = _warning(
        retrieved_at=started,
        source_id="finite",
        valid_to=started + timedelta(minutes=2),
    )
    indefinite = _warning(
        retrieved_at=started,
        source_id="indefinite",
        valid_to=datetime.max.replace(tzinfo=UTC),
    )
    persist_warning_snapshot(
        [baseline, finite, indefinite],
        source_key="warningsmeteo",
        retrieved_at=started,
        parser_warnings=[],
    )

    observed_at = started + timedelta(minutes=5)
    created = _warning(
        retrieved_at=observed_at,
        source_id="created",
        published_at=started + timedelta(minutes=3),
    )
    appeared = _warning(
        retrieved_at=observed_at,
        source_id="appeared",
        published_at=started - timedelta(hours=1),
    )
    corrected = baseline.model_copy(
        update={
            "level": 2,
            "valid_to": baseline.valid_to + timedelta(hours=1),
            "source": baseline.source.model_copy(update={"retrieved_at": observed_at}),
            "raw": {
                "id": "changing",
                "level": "2",
                "typ_zmiany": "korekta",
            },
        }
    )
    finite_later = finite.model_copy(
        update={"source": finite.source.model_copy(update={"retrieved_at": observed_at})}
    )
    indefinite_later = indefinite.model_copy(
        update={
            "source": indefinite.source.model_copy(update={"retrieved_at": observed_at})
        }
    )
    persist_warning_snapshot(
        [corrected, finite_later, indefinite_later, created, appeared],
        source_key="warningsmeteo",
        retrieved_at=observed_at,
        parser_warnings=[],
    )

    signal_at = observed_at + timedelta(minutes=5)
    cancelled = corrected.model_copy(
        update={
            "source": corrected.source.model_copy(update={"retrieved_at": signal_at}),
            "raw": {"id": "changing", "level": "2", "odwolane": True},
        }
    )
    persist_warning_snapshot(
        [cancelled, indefinite_later, created, appeared],
        source_key="warningsmeteo",
        retrieved_at=signal_at,
        parser_warnings=[],
    )

    assert len(list_warning_events(change_kind="created")["events"]) == 1
    assert len(list_warning_events(change_kind="appeared_in_source")["events"]) == 1
    assert len(list_warning_events(change_kind="expired")["events"]) == 1
    assert len(list_warning_events(change_kind="downgraded")["events"]) == 1
    assert len(list_warning_events(change_kind="correction")["events"]) == 1
    cancellation = list_warning_events(change_kind="cancelled")["events"]
    assert len(cancellation) == 1
    assert cancellation[0]["classification_basis"] == "explicit_source_signal"
    assert cancellation[0]["confidence"] == "confirmed"
    assert cancellation[0]["history_status"] == "cancelled"
    assert all(
        event["warning"]["source_id"] != "indefinite"
        for event in list_warning_events(change_kind="expired")["events"]
    )


def test_hydro_identity_includes_exact_office_and_conflicts_are_visible(
    monkeypatch, tmp_path
) -> None:
    _prepare(monkeypatch, tmp_path)
    observed = datetime(2026, 7, 27, 10, tzinfo=UTC)
    first = _warning(
        retrieved_at=observed,
        source_key="warningshydro",
        source_id="72",
        office="BPH Kraków",
        area="Z_K_MA_1",
    )
    other_office = _warning(
        retrieved_at=observed,
        source_key="warningshydro",
        source_id="72",
        office="BPH Wrocław",
        area="Z_W_DS_1",
    )
    result = persist_warning_snapshot(
        [first, other_office],
        source_key="warningshydro",
        retrieved_at=observed,
        parser_warnings=[],
    )

    histories = get_engine().execute(
        "SELECT history_id FROM warning_histories ORDER BY history_id"
    ).fetchall()
    assert result.conflicting_duplicates == 0
    assert len(histories) == 2

    conflict = first.model_copy(update={"content": "Sprzeczna wersja."})
    conflict_result = persist_warning_snapshot(
        [first, conflict, other_office],
        source_key="warningshydro",
        retrieved_at=observed + timedelta(minutes=5),
        parser_warnings=[],
    )
    conflict_events = list_warning_events(change_kind="duplicate_conflict")["events"]
    filtered_conflicts = list_warning_events(
        change_kind="duplicate_conflict",
        area="Z_K_MA_1",
    )["events"]
    assert conflict_result.completeness == "partial"
    assert conflict_result.conflicting_duplicates == 2
    assert len(conflict_events) == 1
    assert len(filtered_conflicts) == 1
    assert conflict_events[0]["identity_status"] == "exact"
    assert conflict_events[0]["history_status"] == "ambiguous"
    assert conflict_events[0]["snapshot"]["completeness"] == "partial"


def test_hydro_special_level_is_not_ranked_and_missing_office_is_ambiguous(
    monkeypatch, tmp_path
) -> None:
    _prepare(monkeypatch, tmp_path)
    observed = datetime(2026, 7, 27, 10, tzinfo=UTC)
    drought = _warning(
        retrieved_at=observed,
        source_key="warningshydro",
        source_id="80",
        office="BPH Kraków",
        level=-1,
        area="Z_K_MA_1",
    )
    missing_office = _warning(
        retrieved_at=observed,
        source_key="warningshydro",
        source_id="81",
        office=None,
        area="Z_K_MA_2",
    )
    persist_warning_snapshot(
        [drought, missing_office],
        source_key="warningshydro",
        retrieved_at=observed,
        parser_warnings=[],
    )
    changed_at = observed + timedelta(minutes=5)
    changed = drought.model_copy(
        update={
            "level": 1,
            "source": drought.source.model_copy(update={"retrieved_at": changed_at}),
            "raw": {"numer": "80", "stopień": "1"},
        }
    )
    persist_warning_snapshot(
        [changed, missing_office],
        source_key="warningshydro",
        retrieved_at=changed_at,
        parser_warnings=[],
    )

    updates = list_warning_events(change_kind="updated")["events"]
    assert len(updates) == 1
    assert "escalated" not in updates[0]["change_kinds"]
    assert "downgraded" not in updates[0]["change_kinds"]
    ambiguous = get_engine().execute(
        "SELECT identity_status FROM warning_histories WHERE source_id = '81'"
    ).fetchone()
    assert ambiguous["identity_status"] == "ambiguous"


def test_reused_key_creates_new_generation_only_with_new_source_time(
    monkeypatch, tmp_path
) -> None:
    _prepare(monkeypatch, tmp_path)
    started = datetime(2026, 7, 27, 10, tzinfo=UTC)
    original = _warning(
        retrieved_at=started,
        source_id="recycled",
        valid_to=started + timedelta(hours=1),
    )
    persist_warning_snapshot(
        [original],
        source_key="warningsmeteo",
        retrieved_at=started,
        parser_warnings=[],
    )
    for minutes in (65, 70):
        persist_warning_snapshot(
            [],
            source_key="warningsmeteo",
            retrieved_at=started + timedelta(minutes=minutes),
            parser_warnings=[],
        )

    reissued_at = started + timedelta(hours=2)
    reissued = _warning(
        retrieved_at=reissued_at,
        source_id="recycled",
        published_at=reissued_at - timedelta(minutes=5),
        valid_from=reissued_at,
        valid_to=reissued_at + timedelta(hours=2),
    )
    persist_warning_snapshot(
        [reissued],
        source_key="warningsmeteo",
        retrieved_at=reissued_at,
        parser_warnings=[],
    )

    generations = get_engine().execute(
        "SELECT generation FROM warning_histories "
        "WHERE source_id = 'recycled' ORDER BY generation"
    ).fetchall()
    assert [row["generation"] for row in generations] == [1, 2]
    assert len(list_warning_events(change_kind="created")["events"]) == 1


def test_event_filters_cursor_and_prospective_api(monkeypatch, tmp_path) -> None:
    settings = _prepare(monkeypatch, tmp_path)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    observed = datetime(2026, 7, 27, 10, tzinfo=UTC)
    warning = _warning(retrieved_at=observed)
    persist_warning_snapshot(
        [warning],
        source_key="warningsmeteo",
        retrieved_at=observed,
        parser_warnings=[],
    )
    second = _warning(
        retrieved_at=observed + timedelta(minutes=5),
        source_id="meteo-2",
        office="CBPM Kraków",
        event="Upał",
        area="1261",
    )
    persist_warning_snapshot(
        [warning, second],
        source_key="warningsmeteo",
        retrieved_at=observed + timedelta(minutes=5),
        parser_warnings=[],
    )

    first_page = list_warning_events(limit=1)
    second_page = list_warning_events(limit=1, cursor=first_page["next_cursor"])
    filtered = list_warning_events(phenomenon="upał", office="kraków", area="1261")
    assert first_page["events"][0]["event_id"] != second_page["events"][0]["event_id"]
    assert len(filtered["events"]) == 1

    with TestClient(app) as client:
        feed = client.get("/api/v1/warning-events?phenomenon=upa%C5%82")
        history_id = feed.json()["events"][0]["history_id"]
        detail = client.get(f"/api/v1/warning-histories/{history_id}")
        export = client.get("/api/v1/export/warning-events.csv?phenomenon=upa%C5%82")
        json_export = client.get(
            "/api/v1/export/warning-events.json?phenomenon=upa%C5%82"
        )
        invalid_cursor = client.get("/api/v1/warning-events?cursor=%25%25%25")
    assert feed.status_code == 200
    assert feed.json()["history_started_at"] is not None
    assert detail.status_code == 200
    assert detail.json()["history_is_prospective"] is True
    assert "Źródło danych: IMGW-PIB." in export.text
    assert json_export.json()["history_started_at"] == "2026-07-27T10:00:00+00:00"
    assert len(json_export.json()["events"]) == 1
    assert invalid_cursor.status_code == 422


def test_prune_is_dry_run_first_and_keeps_active_histories(monkeypatch, tmp_path) -> None:
    _prepare(monkeypatch, tmp_path)
    started = datetime(2025, 1, 1, 10, tzinfo=UTC)
    warning = _warning(
        retrieved_at=started,
        valid_to=started + timedelta(hours=1),
    )
    persist_warning_snapshot(
        [warning],
        source_key="warningsmeteo",
        retrieved_at=started,
        parser_warnings=[],
    )
    persist_warning_snapshot(
        [],
        source_key="warningsmeteo",
        retrieved_at=started + timedelta(hours=2),
        parser_warnings=[],
    )
    persist_warning_snapshot(
        [],
        source_key="warningsmeteo",
        retrieved_at=started + timedelta(hours=3),
        parser_warnings=[],
    )
    active = _warning(
        retrieved_at=datetime(2026, 7, 27, 10, tzinfo=UTC),
        source_id="active",
    )
    persist_warning_snapshot(
        [active],
        source_key="warningsmeteo",
        retrieved_at=active.source.retrieved_at,
        parser_warnings=[],
    )

    dry_run = prune_warning_histories(before=date(2026, 1, 1))
    assert dry_run["histories"] == 1
    assert dry_run["snapshots"] == 2
    assert dry_run["confirmed"] is False
    assert get_engine().execute("SELECT COUNT(*) FROM warning_histories").fetchone()[0] == 2

    connection = get_engine()
    before_failed_prune = tuple(
        connection.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM warning_histories), "
            "(SELECT COUNT(*) FROM warning_versions), "
            "(SELECT COUNT(*) FROM warning_events), "
            "(SELECT COUNT(*) FROM warning_snapshots)"
        ).fetchone()
    )
    connection.execute(
        """
        CREATE TRIGGER fail_warning_history_prune
        BEFORE DELETE ON warning_histories
        WHEN OLD.source_id = 'meteo-1'
        BEGIN
            SELECT RAISE(ABORT, 'injected prune failure');
        END
        """
    )
    connection.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected prune failure"):
        prune_warning_histories(before=date(2026, 1, 1), confirm=True)
    after_failed_prune = tuple(
        connection.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM warning_histories), "
            "(SELECT COUNT(*) FROM warning_versions), "
            "(SELECT COUNT(*) FROM warning_events), "
            "(SELECT COUNT(*) FROM warning_snapshots)"
        ).fetchone()
    )
    assert after_failed_prune == before_failed_prune
    connection.execute("DROP TRIGGER fail_warning_history_prune")
    connection.commit()

    confirmed = prune_warning_histories(before=date(2026, 1, 1), confirm=True)
    assert confirmed["histories"] == 1
    remaining = get_engine().execute(
        "SELECT source_id, status FROM warning_histories"
    ).fetchall()
    assert [(row["source_id"], row["status"]) for row in remaining] == [
        ("active", "active")
    ]
    assert get_engine().execute("SELECT COUNT(*) FROM warning_snapshots").fetchone()[0] == 1
