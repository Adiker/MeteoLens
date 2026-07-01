import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.imgw.refresh import refresh_sources

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.sync_on_startup:
        results = await refresh_sources(
            base_url=str(settings.imgw_base_url),
            cache_dir=settings.cache_dir,
        )
        for result in results:
            if result.status == "success":
                logger.info(
                    "Refreshed IMGW source %s with %s records.",
                    result.source_key,
                    result.record_count,
                )
            else:
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
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(v1_router)
    return app


app = create_app()
