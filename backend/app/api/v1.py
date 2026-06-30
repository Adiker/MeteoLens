from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.imgw.cache import CacheStatus, SourceCache
from app.imgw.sources import SOURCE_DEFINITIONS

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
