import httpx
import pytest

from app.imgw.client import ImgwClient, ImgwClientError
from app.imgw.sources import SOURCE_BY_KEY


@pytest.mark.asyncio
async def test_imgw_client_retries_5xx_responses() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json=[{"id_stacji": "12295"}], request=request)

    client = ImgwClient(
        base_url="https://example.test",
        max_retries=1,
        retry_delay_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    fetch = await client.fetch_json(SOURCE_BY_KEY["synop"])

    assert calls == 2
    assert fetch.status_code == 200
    assert fetch.payload == [{"id_stacji": "12295"}]


@pytest.mark.asyncio
async def test_imgw_client_retries_transport_errors() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("connection reset", request=request)
        return httpx.Response(200, json=[], request=request)

    client = ImgwClient(
        base_url="https://example.test",
        max_retries=1,
        retry_delay_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    fetch = await client.fetch_json(SOURCE_BY_KEY["synop"])

    assert calls == 2
    assert fetch.payload == []


@pytest.mark.asyncio
async def test_imgw_client_does_not_retry_4xx_responses() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, request=request)

    client = ImgwClient(
        base_url="https://example.test",
        max_retries=2,
        retry_delay_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ImgwClientError):
        await client.fetch_json(SOURCE_BY_KEY["synop"])

    assert calls == 1
