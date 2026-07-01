import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.core.config import Settings
from app.imgw.cache import SourceCache
from app.imgw.client import ImgwClient
from app.imgw.refresh import refresh_source
from app.imgw.sources import SOURCE_BY_KEY
from app.main import app
from tests.settings_helpers import apply_test_settings


@pytest.mark.asyncio
async def test_refresh_source_fetches_parses_and_writes_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.db.engine.get_settings",
        lambda: Settings(
            cache_dir=tmp_path,
            database_url=f"sqlite:///{tmp_path / 'test.sqlite3'}",
        ),
    )
    from app.db.engine import reset_engine_cache

    reset_engine_cache()
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id_stacji": "12295",
                    "stacja": "Białystok",
                    "data_pomiaru": "2026-07-01",
                    "godzina_pomiaru": "9",
                    "temperatura": "27.6",
                    "predkosc_wiatru": "3",
                    "kierunek_wiatru": "310",
                    "wilgotnosc_wzgledna": "57.1",
                    "suma_opadu": "0",
                    "cisnienie": "1014.4",
                }
            ],
            request=request,
        )

    cache = SourceCache(tmp_path)
    client = ImgwClient(
        base_url="https://example.test",
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )

    result = await refresh_source(source=SOURCE_BY_KEY["synop"], client=client, cache=cache)

    cached = cache.read("synop")
    assert result.status == "success"
    assert result.record_count == 1
    assert cached is not None
    assert cached.record_count == 1
    assert cached.normalized_payload[0]["id"] == "synop:12295"
    assert cached.error is None


@pytest.mark.asyncio
async def test_refresh_source_records_error_without_masking_it(tmp_path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection reset", request=request)

    cache = SourceCache(tmp_path)
    client = ImgwClient(
        base_url="https://example.test",
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )

    result = await refresh_source(source=SOURCE_BY_KEY["hydro"], client=client, cache=cache)

    status = cache.status("hydro", ttl_seconds=600)
    assert result.status == "error"
    assert result.error == "connection reset"
    assert status.status == "error"
    assert status.error == "connection reset"


def test_app_lifespan_runs_startup_refresh_when_enabled(monkeypatch, tmp_path) -> None:
    calls = []

    async def fake_refresh_sources(*, base_url: str, cache_dir):
        calls.append((base_url, cache_dir))
        return []

    apply_test_settings(
        monkeypatch,
        Settings(
            imgw_base_url="https://example.test",
            cache_dir=tmp_path,
            database_url=f"sqlite:///{tmp_path / 'test.sqlite3'}",
            sync_on_startup=True,
        ),
    )
    monkeypatch.setattr(main, "refresh_sources", fake_refresh_sources)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

    assert calls == [("https://example.test/", tmp_path)]
