import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.core.config import Settings
from app.imgw.cache import SourceCache
from app.imgw.client import ImgwClient
from app.imgw.refresh import SourceRefreshResult, refresh_source
from app.imgw.scheduler import (
    RefreshScheduler,
    interval_seconds_for_source,
    run_source_refresh_loop,
)
from app.imgw.sources import SOURCE_BY_KEY, SOURCE_DEFINITIONS
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

    async def fake_refresh_sources(*, base_url: str, cache_dir, **kwargs):
        calls.append((base_url, cache_dir, kwargs))
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

    assert calls[0][0] == "https://example.test/"
    assert calls[0][1] == tmp_path
    assert calls[0][2]["timeout_seconds"] == 20.0


def test_interval_seconds_for_source_uses_settings_overrides() -> None:
    settings = Settings(
        refresh_synop_seconds=120,
        refresh_hydro_seconds=180,
        refresh_meteo_seconds=240,
        refresh_warnings_seconds=60,
    )

    assert interval_seconds_for_source(SOURCE_BY_KEY["synop"], settings) == 120
    assert interval_seconds_for_source(SOURCE_BY_KEY["hydro"], settings) == 180
    assert interval_seconds_for_source(SOURCE_BY_KEY["meteo"], settings) == 240
    assert interval_seconds_for_source(SOURCE_BY_KEY["warningsmeteo"], settings) == 60
    assert interval_seconds_for_source(SOURCE_BY_KEY["warningshydro"], settings) == 60
    # Sources without a dedicated setting fall back to their default TTL.
    assert (
        interval_seconds_for_source(SOURCE_BY_KEY["product"], settings)
        == SOURCE_BY_KEY["product"].default_ttl_seconds
    )


@pytest.mark.asyncio
async def test_run_source_refresh_loop_refreshes_until_stopped() -> None:
    stop_event = asyncio.Event()
    refreshed = asyncio.Event()
    calls = 0

    async def fake_refresh() -> SourceRefreshResult:
        nonlocal calls
        calls += 1
        if calls >= 2:
            refreshed.set()
        return SourceRefreshResult(source_key="synop", status="success")

    task = asyncio.create_task(
        run_source_refresh_loop(
            source_key="synop",
            interval_seconds=0.01,
            refresh=fake_refresh,
            stop_event=stop_event,
        )
    )
    await asyncio.wait_for(refreshed.wait(), timeout=5)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)

    assert calls >= 2


@pytest.mark.asyncio
async def test_run_source_refresh_loop_survives_refresh_errors() -> None:
    stop_event = asyncio.Event()
    recovered = asyncio.Event()
    calls = 0

    async def flaky_refresh() -> SourceRefreshResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        recovered.set()
        return SourceRefreshResult(source_key="hydro", status="success")

    task = asyncio.create_task(
        run_source_refresh_loop(
            source_key="hydro",
            interval_seconds=0.01,
            refresh=flaky_refresh,
            stop_event=stop_event,
        )
    )
    await asyncio.wait_for(recovered.wait(), timeout=5)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)

    assert calls >= 2


@pytest.mark.asyncio
async def test_refresh_scheduler_starts_and_stops_a_task_per_source(tmp_path) -> None:
    scheduler = RefreshScheduler(
        settings=Settings(imgw_base_url="https://example.test", cache_dir=tmp_path)
    )

    scheduler.start()
    tasks = list(scheduler._tasks)
    assert len(tasks) == len(SOURCE_DEFINITIONS)

    await scheduler.stop()
    assert scheduler._tasks == []
    assert all(task.done() for task in tasks)
