"""Seed a SourceCache directory from the parser test fixtures for E2E runs.

Not part of the application; used only to give the frontend's Playwright
suite a realistic, offline cache to render against instead of hitting the
real IMGW-PIB endpoints.
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.imgw.cache import SourceCache
from app.imgw.parsers import parse_source
from app.normalization.models import SourceMetadata, Warning
from app.services.warning_history import persist_warning_snapshot
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
        warnings = [record for record in result.records if isinstance(record, Warning)]
        if warnings:
            persist_warning_snapshot(
                warnings,
                source_key=source_key,
                retrieved_at=retrieved_at,
                parser_warnings=result.warnings,
            )
            if source_key == "warningsmeteo":
                changed_at = retrieved_at + timedelta(minutes=5)
                changed = warnings[0].model_copy(
                    update={
                        "level": 3 if warnings[0].level != 3 else 2,
                        "source": warnings[0].source.model_copy(
                            update={"retrieved_at": changed_at}
                        ),
                    }
                )
                changed_warnings = [changed, *warnings[1:]]
                persist_warning_snapshot(
                    changed_warnings,
                    source_key=source_key,
                    retrieved_at=changed_at,
                    parser_warnings=[],
                )
                for minutes in (10, 15):
                    persist_warning_snapshot(
                        warnings[1:],
                        source_key=source_key,
                        retrieved_at=retrieved_at + timedelta(minutes=minutes),
                        parser_warnings=[],
                    )


if __name__ == "__main__":
    seed(Path(sys.argv[1]))
