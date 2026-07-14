from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from tests.settings_helpers import apply_test_settings


def test_health_endpoint_returns_ok() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "meteolens-backend"
    assert payload["version"] == "0.1.0-alpha"
    assert "checked_at" in payload


def test_ready_is_degraded_not_unready_when_imgw_cache_is_empty(monkeypatch, tmp_path) -> None:
    settings = Settings(
        cache_dir=tmp_path / "cache",
        geometry_dir=tmp_path / "geometry",
        database_url=f"sqlite:///{tmp_path / 'meteolens.sqlite3'}",
    )
    apply_test_settings(monkeypatch, settings)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["database"]["status"] == "pass"
    assert payload["checks"]["sources"]["status"] == "degraded"


def test_metrics_are_internal_and_request_id_is_returned(monkeypatch, tmp_path) -> None:
    settings = Settings(
        cache_dir=tmp_path / "cache",
        geometry_dir=tmp_path / "geometry",
        database_url=f"sqlite:///{tmp_path / 'meteolens.sqlite3'}",
        metrics_enabled=True,
    )
    apply_test_settings(monkeypatch, settings)

    response = TestClient(app).get("/metrics", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request"
    assert "meteolens_http_requests_total" in response.text
    assert "meteolens_source_status" in response.text
