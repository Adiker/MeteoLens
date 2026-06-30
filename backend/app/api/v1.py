from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.imgw.cache import CacheStatus, SourceCache
from app.imgw.client import ImgwClient, ImgwClientError
from app.imgw.parsers import parse_source
from app.imgw.sources import SOURCE_BY_KEY, SOURCE_DEFINITIONS
from app.normalization.models import SourceMetadata

router = APIRouter(prefix="/api/v1", tags=["v1"])


class SourceDescriptor(BaseModel):
    key: str
    title: str
    url: str
    parser_status: str
    cache_status: str
    cache: CacheStatus
    notes: str | None = None


class SourcesResponse(BaseModel):
    retrieved_at: datetime
    sources: list[SourceDescriptor]


class RefreshResponse(BaseModel):
    source_key: str
    url: str
    retrieved_at: datetime
    status_code: int
    elapsed_ms: int
    record_count: int
    parser_warnings: list[str]
    cache_status: CacheStatus


@router.get("/sources", response_model=SourcesResponse)
def list_sources() -> SourcesResponse:
    settings = get_settings()
    base_url = str(settings.imgw_base_url).rstrip("/")
    cache = SourceCache(settings.cache_dir)
    sources = []
    for source in SOURCE_DEFINITIONS:
        cache_status = cache.status(
            source.key,
            ttl_seconds=source.default_ttl_seconds,
        )
        sources.append(
            SourceDescriptor(
                key=source.key,
                title=source.title,
                url=source.url(base_url),
                parser_status=source.parser_status,
                cache_status=cache_status.status,
                cache=cache_status,
                notes=source.notes,
            )
        )
    return SourcesResponse(retrieved_at=datetime.now(UTC), sources=sources)


@router.post("/sources/{source_key}/refresh", response_model=RefreshResponse)
async def refresh_source(source_key: str) -> RefreshResponse:
    settings = get_settings()
    source = SOURCE_BY_KEY.get(source_key)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source_key}")

    client = ImgwClient(base_url=str(settings.imgw_base_url))
    cache = SourceCache(settings.cache_dir)

    try:
        fetch = await client.fetch_json(source)
        source_metadata = SourceMetadata(
            source_key=source.key,
            url=fetch.url,
            retrieved_at=fetch.retrieved_at,
        )
        parse_result = parse_source(source.key, fetch.payload, source_metadata)
    except ImgwClientError as exc:
        cache.write_error(source_key=source.key, error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    normalized_payload = [
        record.model_dump(mode="json")
        for record in parse_result.records
    ]
    cache.write_success(
        source_key=source.key,
        url=fetch.url,
        retrieved_at=fetch.retrieved_at,
        raw_payload=fetch.payload,
        normalized_payload=normalized_payload,
        parser_warnings=parse_result.warnings,
    )

    return RefreshResponse(
        source_key=source.key,
        url=fetch.url,
        retrieved_at=fetch.retrieved_at,
        status_code=fetch.status_code,
        elapsed_ms=fetch.elapsed_ms,
        record_count=len(parse_result.records),
        parser_warnings=parse_result.warnings,
        cache_status=cache.status(source.key, ttl_seconds=source.default_ttl_seconds),
    )
