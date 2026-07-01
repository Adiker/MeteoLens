import json
from datetime import UTC, datetime

from app.imgw.cache import SourceCache


def test_source_cache_reports_fresh_success(tmp_path) -> None:
    cache = SourceCache(tmp_path)
    cache.write_success(
        source_key="synop",
        url="https://danepubliczne.imgw.pl/api/data/synop",
        retrieved_at=datetime.now(UTC),
        raw_payload=[{"id_stacji": "12295"}],
        normalized_payload=[{"id": "synop:12295"}],
        parser_warnings=[],
    )

    status = cache.status("synop", ttl_seconds=600)

    assert status.status == "fresh"
    assert status.record_count == 1
    assert status.error is None


def test_source_cache_reports_errors(tmp_path) -> None:
    cache = SourceCache(tmp_path)
    cache.write_error(source_key="hydro", error="timeout")

    status = cache.status("hydro", ttl_seconds=600)

    assert status.status == "error"
    assert status.error == "timeout"


def test_source_cache_status_reports_invalid_for_corrupt_file(tmp_path) -> None:
    cache = SourceCache(tmp_path)
    (tmp_path / "synop.json").write_text("not-json", encoding="utf-8")

    status = cache.status("synop", ttl_seconds=600)

    assert status.status == "invalid"
    assert status.error is not None


def test_write_error_ignores_corrupt_existing_cache_file(tmp_path) -> None:
    cache = SourceCache(tmp_path)
    (tmp_path / "synop.json").write_text("not-json", encoding="utf-8")

    cache.write_error(source_key="synop", error="timeout")

    payload = json.loads((tmp_path / "synop.json").read_text(encoding="utf-8"))
    assert payload["error"] == "timeout"
    assert payload["raw_payload"] is None


def test_write_error_twice_without_success_keeps_error_only(tmp_path) -> None:
    cache = SourceCache(tmp_path)
    cache.write_error(source_key="synop", error="first timeout")
    cache.write_error(source_key="synop", error="second timeout")

    status = cache.status("synop", ttl_seconds=600)
    assert status.status == "error"
    assert status.error == "second timeout"


def test_source_cache_preserves_last_success_on_error(tmp_path) -> None:
    cache = SourceCache(tmp_path)
    retrieved_at = datetime.now(UTC)
    cache.write_success(
        source_key="synop",
        url="https://danepubliczne.imgw.pl/api/data/synop",
        retrieved_at=retrieved_at,
        raw_payload=[{"id_stacji": "12295"}],
        normalized_payload=[{"id": "synop:12295"}],
        parser_warnings=["minor parser warning"],
    )

    cache.write_error(source_key="synop", error="timeout")

    payload = json.loads((tmp_path / "synop.json").read_text(encoding="utf-8"))
    status = cache.status("synop", ttl_seconds=600)
    assert payload["raw_payload"] == [{"id_stacji": "12295"}]
    assert payload["normalized_payload"] == [{"id": "synop:12295"}]
    assert payload["record_count"] == 1
    assert payload["error"] == "timeout"
    assert status.status == "stale"
    assert status.last_success_at == retrieved_at
    assert status.record_count == 1
    assert status.parser_warnings == ["minor parser warning"]
    assert status.error == "timeout"
