import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging, log_api_error
from app.db.engine import init_db
from app.imgw.refresh import refresh_sources
from app.services.observation_history import prune_history

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    logger.info(
        "Starting %s v%s env=%s cache_dir=%s sync_on_startup=%s",
        settings.service_name,
        settings.version,
        settings.env,
        settings.cache_dir,
        settings.sync_on_startup,
    )
    init_db()
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
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="MeteoLens API",
        version=settings.version,
        description="Backend API for MeteoLens public IMGW-PIB data visualisation.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

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
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    app.include_router(health_router)
    app.include_router(v1_router)
    return app


app = create_app()
