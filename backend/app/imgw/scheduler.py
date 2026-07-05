import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence

from app.core.config import Settings
from app.imgw.cache import SourceCache
from app.imgw.client import ImgwClient
from app.imgw.refresh import SourceRefreshResult, refresh_source
from app.imgw.sources import SOURCE_DEFINITIONS, SourceDefinition
from app.products.refresh import refresh_product_details

logger = logging.getLogger(__name__)


def interval_seconds_for_source(source: SourceDefinition, settings: Settings) -> int:
    overrides = {
        "synop": settings.refresh_synop_seconds,
        "hydro": settings.refresh_hydro_seconds,
        "meteo": settings.refresh_meteo_seconds,
        "warningsmeteo": settings.refresh_warnings_seconds,
        "warningshydro": settings.refresh_warnings_seconds,
    }
    return overrides.get(source.key, source.default_ttl_seconds)


async def run_source_refresh_loop(
    *,
    source_key: str,
    interval_seconds: float,
    refresh: Callable[[], Awaitable[SourceRefreshResult]],
    stop_event: asyncio.Event,
) -> None:
    # The first refresh happens one full interval after startup; initial
    # freshness is covered by the METEOLENS_SYNC_ON_STARTUP path.
    while True:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            return
        except TimeoutError:
            pass
        try:
            result = await refresh()
        except Exception:
            logger.exception("Scheduled refresh of %s crashed.", source_key)
            continue
        if result.status != "success":
            logger.warning(
                "Scheduled refresh of %s failed: %s", source_key, result.error
            )


async def run_product_detail_refresh_loop(
    *,
    settings: Settings,
    stop_event: asyncio.Event,
) -> None:
    # Startup freshness is covered by METEOLENS_SYNC_ON_STARTUP; the loop
    # waits one full interval first, mirroring run_source_refresh_loop.
    while True:
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=settings.product_detail_cache_seconds,
            )
            return
        except TimeoutError:
            pass
        try:
            results = await refresh_product_details(settings)
        except Exception:
            logger.exception("Scheduled product detail refresh crashed.")
            continue
        for result in results:
            if result.status == "error":
                logger.warning(
                    "Scheduled product detail refresh of %s failed: %s",
                    result.product_id,
                    result.error,
                )


class RefreshScheduler:
    """Periodically refreshes IMGW source caches while the app is running."""

    def __init__(
        self,
        *,
        settings: Settings,
        sources: Sequence[SourceDefinition] = SOURCE_DEFINITIONS,
    ) -> None:
        self._settings = settings
        self._sources = sources
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    def start(self) -> None:
        settings = self._settings
        cache = SourceCache(settings.cache_dir)
        client = ImgwClient(
            base_url=str(settings.imgw_base_url),
            timeout_seconds=settings.imgw_timeout_seconds,
            max_retries=settings.imgw_max_retries,
            retry_delay_seconds=settings.imgw_retry_delay_seconds,
        )
        for source in self._sources:
            interval = interval_seconds_for_source(source, settings)

            def make_refresh(
                source: SourceDefinition = source,
            ) -> Callable[[], Awaitable[SourceRefreshResult]]:
                def refresh() -> Awaitable[SourceRefreshResult]:
                    return refresh_source(source=source, client=client, cache=cache)

                return refresh

            self._tasks.append(
                asyncio.create_task(
                    run_source_refresh_loop(
                        source_key=source.key,
                        interval_seconds=interval,
                        refresh=make_refresh(),
                        stop_event=self._stop_event,
                    ),
                    name=f"refresh-{source.key}",
                )
            )
            logger.info(
                "Scheduled %s refresh every %s seconds.", source.key, interval
            )

        if settings.product_refresh_enabled and settings.product_refresh_id_list:
            self._tasks.append(
                asyncio.create_task(
                    run_product_detail_refresh_loop(
                        settings=settings,
                        stop_event=self._stop_event,
                    ),
                    name="refresh-product-details",
                )
            )
            logger.info(
                "Scheduled product detail refresh for %s every %s seconds.",
                ",".join(settings.product_refresh_id_list),
                settings.product_detail_cache_seconds,
            )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
