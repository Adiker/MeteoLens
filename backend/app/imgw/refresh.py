import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.imgw.cache import SourceCache
from app.imgw.client import ImgwClient
from app.imgw.parsers import parse_source
from app.imgw.sources import SOURCE_DEFINITIONS, SourceDefinition
from app.normalization.models import SourceMetadata


@dataclass(frozen=True)
class SourceRefreshResult:
    source_key: str
    status: str
    record_count: int = 0
    parser_warnings: list[str] = field(default_factory=list)
    error: str | None = None


async def refresh_source(
    *,
    source: SourceDefinition,
    client: ImgwClient,
    cache: SourceCache,
) -> SourceRefreshResult:
    try:
        fetch = await client.fetch_json(source)
        metadata = SourceMetadata(
            source_key=source.key,
            url=fetch.url,
            retrieved_at=fetch.retrieved_at,
        )
        parse_result = parse_source(source.key, fetch.payload, metadata)
        normalized_payload = [
            record.model_dump(mode="json") for record in parse_result.records
        ]
        cache.write_success(
            source_key=source.key,
            url=fetch.url,
            retrieved_at=fetch.retrieved_at,
            raw_payload=fetch.payload,
            normalized_payload=normalized_payload,
            parser_warnings=parse_result.warnings,
        )
        return SourceRefreshResult(
            source_key=source.key,
            status="success",
            record_count=len(normalized_payload),
            parser_warnings=parse_result.warnings,
        )
    except Exception as exc:
        error = str(exc)
        cache.write_error(source_key=source.key, error=error)
        return SourceRefreshResult(source_key=source.key, status="error", error=error)


async def refresh_sources(
    *,
    base_url: str,
    cache_dir: Path,
    sources: Sequence[SourceDefinition] = SOURCE_DEFINITIONS,
) -> list[SourceRefreshResult]:
    cache = SourceCache(cache_dir)
    client = ImgwClient(base_url=base_url)
    return list(
        await asyncio.gather(
            *(refresh_source(source=source, client=client, cache=cache) for source in sources)
        )
    )
