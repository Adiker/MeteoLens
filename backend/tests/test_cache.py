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

