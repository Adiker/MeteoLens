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
    def __init__(self, *, base_url: str, timeout_seconds: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def fetch_json(self, source: SourceDefinition) -> ImgwFetch:
        url = source.url(self.base_url)
        started = perf_counter()
        retrieved_at = datetime.now(UTC)
        headers = {
            "Accept": "application/json",
            "User-Agent": "MeteoLens/0.1 (+https://github.com/Adiker/MeteoLens)",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ImgwClientError(str(exc), source_key=source.key) from exc

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

