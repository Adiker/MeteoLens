from asyncio import sleep
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx

from app.imgw.sources import SourceDefinition


class ImgwClientError(RuntimeError):
    def __init__(self, message: str, *, source_key: str) -> None:
        super().__init__(message)
        self.source_key = source_key


@dataclass(frozen=True)
class ImgwFetch:
    source_key: str
    url: str
    retrieved_at: datetime
    status_code: int
    elapsed_ms: int
    content_type: str | None
    etag: str | None
    last_modified: str | None
    payload: Any


class ImgwClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        retry_delay_seconds: float = 0.25,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.retry_delay_seconds = retry_delay_seconds
        self.transport = transport

    async def fetch_json(self, source: SourceDefinition) -> ImgwFetch:
        url = source.url(self.base_url)
        started = perf_counter()
        retrieved_at = datetime.now(UTC)
        headers = {
            "Accept": "application/json",
            "User-Agent": "MeteoLens/0.1 (+https://github.com/Adiker/MeteoLens)",
        }

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers=headers,
            transport=self.transport,
        ) as client:
            response = await self._get_with_retries(client, url, source)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ImgwClientError("IMGW response is not valid JSON", source_key=source.key) from exc

        return ImgwFetch(
            source_key=source.key,
            url=url,
            retrieved_at=retrieved_at,
            status_code=response.status_code,
            elapsed_ms=round((perf_counter() - started) * 1000),
            content_type=response.headers.get("content-type"),
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
            payload=payload,
        )

    async def _get_with_retries(
        self,
        client: httpx.AsyncClient,
        url: str,
        source: SourceDefinition,
    ) -> httpx.Response:
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500 or attempt == self.max_retries:
                    raise ImgwClientError(str(exc), source_key=source.key) from exc
            except httpx.TransportError as exc:
                if attempt == self.max_retries:
                    raise ImgwClientError(str(exc), source_key=source.key) from exc

            if self.retry_delay_seconds > 0:
                await sleep(self.retry_delay_seconds)

        raise ImgwClientError("IMGW request failed after retries", source_key=source.key)
