"""Seed a SourceCache directory from the parser test fixtures for E2E runs.

Not part of the application; used only to give the frontend's Playwright
suite a realistic, offline cache to render against instead of hitting the
real IMGW-PIB endpoints.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

from app.imgw.cache import SourceCache
from app.imgw.parsers import parse_source
from app.normalization.models import SourceMetadata
from tests.test_parsers import load_fixture

SOURCE_KEYS = ("synop", "hydro", "meteo", "warningsmeteo", "warningshydro")


def seed(cache_dir: Path) -> None:
    cache = SourceCache(cache_dir)
    retrieved_at = datetime.now(UTC)
    for source_key in SOURCE_KEYS:
        metadata = SourceMetadata(
            source_key=source_key,
            url=f"https://danepubliczne.imgw.pl/api/data/{source_key}",
            retrieved_at=retrieved_at,
        )
        raw_payload = load_fixture(source_key)
        result = parse_source(source_key, raw_payload, metadata)
        cache.write_success(
            source_key=source_key,
            url=metadata.url,
            retrieved_at=retrieved_at,
            raw_payload=raw_payload,
            normalized_payload=[record.model_dump(mode="json") for record in result.records],
            parser_warnings=result.warnings,
        )


if __name__ == "__main__":
    seed(Path(sys.argv[1]))
