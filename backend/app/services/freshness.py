"""Source cache freshness aggregation for dashboards."""

from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.imgw.cache import SourceCache
from app.imgw.sources import SOURCE_DEFINITIONS
from app.normalization.models import ATTRIBUTION, PROCESSED_NOTICE

ALERTING_DISCLAIMER = (
    "MeteoLens nie jest urzędowym systemem ostrzegania. Lokalne reguły, "
    "powiadomienia i porównania służą wyłąnie informacji operacyjnej i nie "
    "zastępują komunikatów IMGW-PIB."
)


def build_freshness_report(settings: Settings) -> dict[str, Any]:
    cache = SourceCache(settings.cache_dir)
    sources: list[dict[str, Any]] = []
    empty_count = 0
    stale_count = 0
    error_count = 0

    for source in SOURCE_DEFINITIONS:
        status = cache.status(source.key, ttl_seconds=source.default_ttl_seconds)
        if status.status == "empty":
            empty_count += 1
        elif status.status in {"stale", "invalid"}:
            stale_count += 1
        elif status.status == "error":
            error_count += 1

        sources.append(
            {
                "source_key": source.key,
                "title": source.title,
                "cache_status": status.status,
                "last_success_at": status.last_success_at,
                "age_seconds": status.age_seconds,
                "record_count": status.record_count,
                "parser_warnings": status.parser_warnings,
                "error": status.error,
                "ttl_seconds": source.default_ttl_seconds,
                "stale": status.status in {"stale", "error", "invalid"},
                "parser_status": source.parser_status,
                "notes": source.notes,
            }
        )

    if empty_count == len(SOURCE_DEFINITIONS):
        overall_status = "empty"
    elif error_count > 0 or empty_count > 0:
        overall_status = "degraded"
    elif stale_count > 0:
        overall_status = "stale"
    else:
        overall_status = "healthy"

    notes: list[str] = []
    if stale_count:
        notes.append(f"{stale_count} source cache entries are stale or invalid.")
    if empty_count:
        notes.append(f"{empty_count} source caches are empty.")
    if error_count:
        notes.append(f"{error_count} source caches report fetch errors.")

    return {
        "generated_at": datetime.now(UTC),
        "overall_status": overall_status,
        "sources": sources,
        "notes": notes,
        "attribution": ATTRIBUTION,
        "processed_notice": PROCESSED_NOTICE,
        "alerting_disclaimer": ALERTING_DISCLAIMER,
    }
