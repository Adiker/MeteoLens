from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.observability import (
    metrics,
    metrics_response,
    observe_runtime_storage,
    observe_source_cache,
)
from app.db.engine import get_engine
from app.imgw.cache import SourceCache
from app.imgw.sources import SOURCE_DEFINITIONS

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    checked_at: datetime


class ReadyCheck(BaseModel):
    status: str
    code: str | None = None


class ReadinessResponse(HealthResponse):
    checks: dict[str, ReadyCheck]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return live()


@router.get("/health/live", response_model=HealthResponse)
def live() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.version,
        environment=settings.env,
        checked_at=datetime.now(UTC),
    )


@router.get("/health/ready", response_model=ReadinessResponse)
def ready(request: Request, response: Response) -> ReadinessResponse:
    settings = get_settings()
    checks = {
        "startup": ReadyCheck(
            status="pass" if getattr(request.app.state, "startup_complete", False) else "fail",
            code=None if getattr(request.app.state, "startup_complete", False) else "starting",
        ),
        "database": _database_check(),
        "data": _data_check(settings.cache_dir.parent),
    }
    core_ready = all(check.status == "pass" for check in checks.values())
    source_statuses = [
        SourceCache(settings.cache_dir).status(source.key, ttl_seconds=source.default_ttl_seconds)
        for source in SOURCE_DEFINITIONS
    ]
    source_degraded = any(state.status != "fresh" for state in source_statuses)
    checks["sources"] = ReadyCheck(
        status="degraded" if source_degraded else "pass",
        code="source_cache_degraded" if source_degraded else None,
    )
    metrics.readiness.set(1 if core_ready else 0)
    if not core_ready:
        response.status_code = 503
        status = "not_ready"
    elif source_degraded:
        status = "degraded"
    else:
        status = "ready"
    return ReadinessResponse(
        status=status,
        service=settings.service_name,
        version=settings.version,
        environment=settings.env,
        checked_at=datetime.now(UTC),
        checks=checks,
    )


@router.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    settings = get_settings()
    if not settings.metrics_enabled:
        return Response(status_code=404)
    observe_source_cache(settings)
    observe_runtime_storage(settings)
    content, content_type = metrics_response()
    return Response(content=content, media_type=content_type)


def _database_check() -> ReadyCheck:
    try:
        get_engine().execute("SELECT 1").fetchone()
    except Exception:
        return ReadyCheck(status="fail", code="database_unavailable")
    return ReadyCheck(status="pass")


def _data_check(data_dir) -> ReadyCheck:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".readiness-probe"
        probe.write_text("ok", encoding="ascii")
        probe.unlink(missing_ok=True)
    except OSError:
        return ReadyCheck(status="fail", code="data_not_writable")
    return ReadyCheck(status="pass")
