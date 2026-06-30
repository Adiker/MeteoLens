from datetime import UTC, datetime

from fastapi.testclient import TestClient

import app.api.v1 as v1
from app.core.config import Settings
from app.imgw.client import ImgwClient, ImgwFetch
from app.main import app
from tests.test_parsers import load_fixture


def test_refresh_source_fetches_parses_and_caches(monkeypatch, tmp_path) -> None:
    settings = Settings(cache_dir=tmp_path, imgw_base_url="https://danepubliczne.imgw.pl")
    monkeypatch.setattr(v1, "get_settings", lambda: settings)

    async def fake_fetch_json(self: ImgwClient, source):  # noqa: ARG001
        return ImgwFetch(
            source_key=source.key,
            url=source.url("https://danepubliczne.imgw.pl"),
            retrieved_at=datetime(2026, 6, 30, 7, 30, tzinfo=UTC),
            status_code=200,
            elapsed_ms=12,
            content_type="application/json",
            etag=None,
            last_modified=None,
            payload=load_fixture("synop"),
        )

    monkeypatch.setattr(ImgwClient, "fetch_json", fake_fetch_json)

    response = TestClient(app).post("/api/v1/sources/synop/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_key"] == "synop"
    assert payload["record_count"] == 2
    assert payload["cache_status"]["status"] == "fresh"
    assert (tmp_path / "synop.json").exists()
