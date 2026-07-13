"""Low-cardinality Prometheus metrics and runtime storage inspection."""

from __future__ import annotations

import shutil
import time
from collections.abc import Iterator
from pathlib import Path

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.core.config import Settings


class MeteoLensMetrics:
    def __init__(self) -> None:
        self.http_requests = Counter(
            "meteolens_http_requests_total",
            "Completed HTTP requests.",
            ("method", "route", "status"),
        )
        self.http_duration = Histogram(
            "meteolens_http_request_duration_seconds",
            "HTTP request duration.",
            ("method", "route"),
        )
        self.source_refreshes = Counter(
            "meteolens_source_refresh_total",
            "IMGW source refresh outcomes.",
            ("source_key", "status", "stage"),
        )
        self.source_refresh_duration = Histogram(
            "meteolens_source_refresh_duration_seconds",
            "IMGW source refresh duration.",
            ("source_key", "status"),
        )
        self.source_age = Gauge(
            "meteolens_source_age_seconds",
            "Age of the last successfully cached source payload.",
            ("source_key",),
        )
        self.source_status = Gauge(
            "meteolens_source_status",
            "One-hot source cache status.",
            ("source_key", "status"),
        )
        self.source_parser_warnings = Gauge(
            "meteolens_source_parser_warnings",
            "Number of parser warnings on the cached source payload.",
            ("source_key",),
        )
        self.product_renders = Counter(
            "meteolens_product_render_total",
            "Product render outcomes.",
            ("product_id", "status", "cache"),
        )
        self.product_render_duration = Histogram(
            "meteolens_product_render_duration_seconds",
            "Product render duration.",
            ("product_id", "status"),
        )
        self.product_render_active = Gauge(
            "meteolens_product_render_active",
            "Active product rendering operations.",
        )
        self.product_render_waiting = Gauge(
            "meteolens_product_render_waiting",
            "Product render operations waiting for the bounded gate.",
        )
        self.product_downloads = Counter(
            "meteolens_product_download_total",
            "Product binary download or binary-cache outcomes.",
            ("product_id", "status", "cache"),
        )
        self.product_download_duration = Histogram(
            "meteolens_product_download_duration_seconds",
            "Product binary download duration.",
            ("product_id", "status"),
        )
        self.archive_imports = Counter(
            "meteolens_archive_import_total",
            "Archive import outcomes.",
            ("source_key", "archive_kind", "status"),
        )
        self.archive_import_duration = Histogram(
            "meteolens_archive_import_duration_seconds",
            "Archive import duration.",
            ("source_key", "archive_kind", "status"),
        )
        self.archive_import_active = Gauge(
            "meteolens_archive_import_active",
            "Archive imports currently marked running.",
        )
        self.storage_bytes = Gauge(
            "meteolens_storage_bytes",
            "Bytes stored in a MeteoLens runtime area.",
            ("area",),
        )
        self.storage_files = Gauge(
            "meteolens_storage_files",
            "Files stored in a MeteoLens runtime area.",
            ("area",),
        )
        self.data_disk_bytes = Gauge(
            "meteolens_data_disk_bytes",
            "Disk usage for the filesystem containing /data.",
            ("state",),
        )
        self.readiness = Gauge(
            "meteolens_readiness",
            "One when core readiness checks pass; source degradation is reported separately.",
        )
        self.last_backup = Gauge(
            "meteolens_last_successful_backup_timestamp_seconds",
            "Timestamp of the last successful local backup, or zero when none exists.",
        )
        self.container_memory_limit = Gauge(
            "meteolens_container_memory_limit_bytes",
            "Container memory limit from cgroup, or zero when unavailable.",
        )
        self.container_cpu_limit = Gauge(
            "meteolens_container_cpu_limit",
            "Container CPU quota in cores, or zero when unavailable.",
        )

    def observe_http(self, *, method: str, route: str, status: int, duration: float) -> None:
        self.http_requests.labels(method=method, route=route, status=str(status)).inc()
        self.http_duration.labels(method=method, route=route).observe(duration)


metrics = MeteoLensMetrics()


def metrics_response() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST


def observe_source_cache(settings: Settings) -> None:
    """Refresh gauges derived from persisted cache state at scrape time."""
    from app.imgw.cache import SourceCache
    from app.imgw.sources import SOURCE_DEFINITIONS

    cache = SourceCache(settings.cache_dir)
    statuses = ("fresh", "stale", "error", "empty", "invalid")
    for source in SOURCE_DEFINITIONS:
        state = cache.status(source.key, ttl_seconds=source.default_ttl_seconds)
        for status in statuses:
            metrics.source_status.labels(source_key=source.key, status=status).set(
                1 if state.status == status else 0
            )
        metrics.source_age.labels(source_key=source.key).set(state.age_seconds or 0)
        metrics.source_parser_warnings.labels(source_key=source.key).set(
            len(state.parser_warnings)
        )


def observe_runtime_storage(settings: Settings) -> None:
    data_dir = settings.cache_dir.parent
    areas = {
        "sqlite": [data_dir / "meteolens.sqlite3", data_dir / "meteolens.sqlite3-wal"],
        "source_cache": [settings.cache_dir],
        "geometry": [settings.geometry_dir],
        "product_binaries": [data_dir / "products" / "binaries"],
        "product_renders": [data_dir / "products" / "renders"],
    }
    for area, paths in areas.items():
        size, files = _paths_size(paths)
        metrics.storage_bytes.labels(area=area).set(size)
        metrics.storage_files.labels(area=area).set(files)
    try:
        usage = shutil.disk_usage(data_dir)
    except OSError:
        return
    metrics.data_disk_bytes.labels(state="total").set(usage.total)
    metrics.data_disk_bytes.labels(state="used").set(usage.used)
    metrics.data_disk_bytes.labels(state="free").set(usage.free)
    metrics.last_backup.set(_last_backup_timestamp(data_dir / ".operations" / "last-backup.json"))
    _observe_cgroup_limits()


def _paths_size(paths: list[Path]) -> tuple[int, int]:
    size = 0
    files = 0
    for path in paths:
        for item in _files_in(path):
            try:
                size += item.stat().st_size
                files += 1
            except OSError:
                continue
    return size, files


def _files_in(path: Path) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    if not path.exists():
        return
    try:
        yield from (item for item in path.rglob("*") if item.is_file())
    except OSError:
        return


def _last_backup_timestamp(path: Path) -> float:
    try:
        import json

        value = json.loads(path.read_text(encoding="utf-8")).get("completed_at")
        if isinstance(value, str):
            from datetime import datetime

            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (OSError, ValueError, TypeError):
        pass
    return 0


def _observe_cgroup_limits() -> None:
    try:
        memory = Path("/sys/fs/cgroup/memory.max").read_text(encoding="ascii").strip()
        metrics.container_memory_limit.set(0 if memory == "max" else int(memory))
    except (OSError, ValueError):
        metrics.container_memory_limit.set(0)
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text(encoding="ascii").split()
        metrics.container_cpu_limit.set(0 if quota == "max" else int(quota) / int(period))
    except (OSError, ValueError):
        metrics.container_cpu_limit.set(0)


def monotonic_seconds() -> float:
    return time.perf_counter()
