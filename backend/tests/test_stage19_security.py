import json
import logging
import socket
import threading
import time
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import JsonFormatter, log_api_error, log_source_fetch
from app.core.security import archive_backfill_gate
from app.main import create_app
from app.products import rendering
from tests.settings_helpers import apply_test_settings


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(
        cache_dir=tmp_path / "cache",
        geometry_dir=tmp_path / "geometry",
        database_url=f"sqlite:///{tmp_path / 'meteolens.sqlite3'}",
        archive_backfill_cooldown_seconds=60,
        **overrides,
    )


def test_admin_backfill_fails_closed_without_configured_token(monkeypatch, tmp_path) -> None:
    settings = _settings(tmp_path, env="production", admin_token=None)
    apply_test_settings(monkeypatch, settings)
    archive_backfill_gate.reset()

    response = TestClient(create_app()).post(
        "/api/v1/archive/backfill/synop-daily?from=2026-05-01&to=2026-05-01"
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "admin_operations_disabled"
    assert settings.frontend_origins == []


def test_admin_backfill_requires_and_accepts_configured_token(monkeypatch, tmp_path) -> None:
    settings = _settings(tmp_path, admin_token="test-admin-token")
    apply_test_settings(monkeypatch, settings)
    archive_backfill_gate.reset()

    class FakeBackfiller:
        def __init__(self, received_settings: Settings) -> None:
            assert received_settings is settings

        def run(self, *, observed_from: date, observed_to: date):
            return type(
                "Result",
                (),
                {
                    "model_dump": lambda self: {
                        "id": "run-1",
                        "source_key": "synop",
                        "archive_kind": "synop_daily",
                        "status": "completed",
                        "started_at": datetime(2026, 5, 1, tzinfo=UTC),
                        "finished_at": datetime(2026, 5, 1, tzinfo=UTC),
                        "observed_from": observed_from,
                        "observed_to": observed_to,
                        "files_total": 1,
                        "files_processed": 1,
                        "rows_seen": 1,
                        "observations_seen": 1,
                        "observations_inserted": 1,
                        "observations_updated": 0,
                        "observations_unchanged": 0,
                        "parser_warnings": [],
                        "errors": [],
                    }
                },
            )()

    monkeypatch.setattr("app.api.v1.SynopDailyArchiveBackfiller", FakeBackfiller)
    client = TestClient(create_app())
    url = "/api/v1/archive/backfill/synop-daily?from=2026-05-01&to=2026-05-01"

    denied = client.post(url)
    allowed = client.post(url, headers={"X-MeteoLens-Admin-Token": "test-admin-token"})
    duplicate = client.post(
        url, headers={"X-MeteoLens-Admin-Token": "test-admin-token"}
    )

    assert denied.status_code == 401
    assert denied.json()["detail"]["error"]["code"] == "admin_authentication_required"
    assert denied.headers["www-authenticate"] == "MeteoLensAdmin"
    assert allowed.status_code == 200
    assert allowed.json()["id"] == "run-1"
    assert duplicate.status_code == 429
    assert duplicate.headers["retry-after"] == "60"


def test_archive_gate_rejects_concurrent_and_duplicate_imports() -> None:
    archive_backfill_gate.reset()
    with archive_backfill_gate.acquire(key="same-range", cooldown_seconds=60):
        with pytest.raises(HTTPException) as concurrent:
            with archive_backfill_gate.acquire(key="other-range", cooldown_seconds=60):
                pass
    with pytest.raises(HTTPException) as duplicate:
        with archive_backfill_gate.acquire(key="same-range", cooldown_seconds=60):
            pass

    assert concurrent.value.status_code == 409
    assert duplicate.value.status_code == 429
    archive_backfill_gate.reset()


def test_production_cors_allows_only_configured_origin(monkeypatch, tmp_path) -> None:
    settings = _settings(
        tmp_path,
        env="production",
        frontend_origin="https://meteolens.example.test",
    )
    apply_test_settings(monkeypatch, settings)
    client = TestClient(create_app())

    allowed = client.get("/health", headers={"Origin": "https://meteolens.example.test"})
    denied = client.get("/health", headers={"Origin": "https://evil.example.test"})

    assert allowed.headers["access-control-allow-origin"] == "https://meteolens.example.test"
    assert "access-control-allow-origin" not in denied.headers
    assert "access-control-allow-credentials" not in allowed.headers


def test_duplicate_render_requests_share_one_uncached_render(monkeypatch, tmp_path) -> None:
    settings = _settings(tmp_path, product_render_max_concurrent=1)
    filename = "202607040000_202607040300_lfff00030000"
    calls = 0
    calls_lock = threading.Lock()

    def fake_uncached(*args, **kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.05)
        png_path = kwargs["png_path"]
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(b"PNG")
        metadata = {"frame_time": "2026-07-04T03:00:00+00:00"}
        png_path.with_suffix(".json").write_text(json.dumps(metadata), encoding="utf-8")
        return rendering.RenderResult(png_path=png_path, metadata=metadata, from_cache=False)

    monkeypatch.setattr(rendering, "_render_uncached", fake_uncached)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))
        ],
    )
    barrier = threading.Barrier(2)
    results: list[rendering.RenderResult] = []

    def request_render() -> None:
        barrier.wait()
        results.append(
            rendering.render_frame(
                settings,
                product_id="COSMO_HVD_00_00",
                filename=filename,
                url=f"https://danepubliczne.imgw.pl/pl/d/{filename}",
                variable_key="t2m",
            )
        )

    threads = [threading.Thread(target=request_render) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls == 1
    assert len(results) == 2
    assert any(result.from_cache for result in results)


def test_logs_redact_tokens_signed_urls_and_precise_query_locations(caplog) -> None:
    caplog.set_level("INFO")
    log_source_fetch(
        source_key="product",
        url="https://example.test/file?X-Amz-Signature=secret",
        status="success",
        retrieved_at="2026-07-11T00:00:00Z",
    )
    log_api_error(
        path="/api/v1/location/summary",
        status_code=400,
        code="bad_request",
        message="Authorization=Bearer-secret token=abc",
    )

    output = caplog.text
    assert "secret" not in output
    assert "Bearer-secret" not in output
    assert "token=abc" not in output
    assert "X-Amz-Signature=%5BREDACTED%5D" in output
    # API logs record route paths rather than query strings, so caller
    # latitude/longitude from location queries cannot reach this helper.
    assert "location/summary?" not in output


def test_json_log_formatter_keeps_request_correlation_and_safe_fields() -> None:
    record = logging.LogRecord(
        "meteolens.source", logging.INFO, __file__, 1, "refresh complete", (), None
    )
    record.request_id = "request-123"
    record.event = "source_fetch"
    record.source_key = "synop"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["request_id"] == "request-123"
    assert payload["event"] == "source_fetch"
    assert payload["source_key"] == "synop"
