import logging
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging, log_api_error, reset_request_id, set_request_id
from app.core.observability import metrics
from app.db.engine import init_db
from app.imgw.archive import mark_interrupted_archive_runs
from app.imgw.refresh import refresh_sources
from app.imgw.scheduler import RefreshScheduler
from app.products.refresh import refresh_product_details
from app.services.observation_history import prune_history

logger = logging.getLogger(__name__)
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    logger.info(
        "Starting %s v%s env=%s cache_dir=%s sync_on_startup=%s refresh_enabled=%s",
        settings.service_name,
        settings.version,
        settings.env,
        settings.cache_dir,
        settings.sync_on_startup,
        settings.refresh_enabled,
    )
    app.state.startup_complete = False
    init_db()
    interrupted = mark_interrupted_archive_runs()
    if interrupted:
        logger.warning("Marked %s interrupted archive imports after restart.", interrupted)
    pruned = prune_history(retention_days=settings.observation_retention_days)
    if pruned:
        logger.info("Pruned %s observation history rows.", pruned)
    if settings.sync_on_startup:
        results = await refresh_sources(
            base_url=str(settings.imgw_base_url),
            cache_dir=settings.cache_dir,
            timeout_seconds=settings.imgw_timeout_seconds,
            max_retries=settings.imgw_max_retries,
            retry_delay_seconds=settings.imgw_retry_delay_seconds,
        )
        for result in results:
            if result.status != "success":
                logger.warning(
                    "Failed to refresh IMGW source %s: %s",
                    result.source_key,
                    result.error,
                )
        if settings.product_refresh_enabled:
            detail_results = await refresh_product_details(settings)
            for detail_result in detail_results:
                if detail_result.status == "error":
                    logger.warning(
                        "Failed to refresh product detail %s: %s",
                        detail_result.product_id,
                        detail_result.error,
                    )
    scheduler: RefreshScheduler | None = None
    if settings.refresh_enabled:
        scheduler = RefreshScheduler(settings=settings)
        scheduler.start()
    app.state.startup_complete = True
    try:
        yield
    finally:
        app.state.startup_complete = False
        if scheduler is not None:
            await scheduler.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="MeteoLens API",
        version=settings.version,
        description="Backend API for MeteoLens public IMGW-PIB data visualisation.",
        lifespan=lifespan,
    )
    app.state.startup_complete = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        # MeteoLens has no browser session/auth cookies. Credentials would make
        # CORS unnecessarily permissive and are intentionally disabled.
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else str(uuid4())
        token = set_request_id(request_id)
        started = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.perf_counter() - started
            route = getattr(request.scope.get("route"), "path", None) or "unmatched"
            status = response.status_code if response is not None else 500
            metrics.observe_http(
                method=request.method,
                route=route,
                status=status,
                duration=duration,
            )
            if response is not None:
                response.headers["X-Request-ID"] = request_id
            reset_request_id(token)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        code = "http_error"
        message = str(detail)
        if isinstance(detail, dict) and "error" in detail:
            error = detail["error"]
            if isinstance(error, dict):
                code = str(error.get("code", code))
                message = str(error.get("message", message))
        log_api_error(
            path=request.url.path,
            status_code=exc.status_code,
            code=code,
            message=message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=exc.headers,
        )

    app.include_router(health_router)
    app.include_router(v1_router)
    return app


app = create_app()
