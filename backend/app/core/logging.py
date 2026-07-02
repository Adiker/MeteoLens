"""Structured logging helpers for production observability."""

from __future__ import annotations

import logging
import sys

from app.core.config import Settings


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


def configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt=(
                "%(asctime)s %(levelname)s %(name)s "
                "request_id=%(request_id)s %(message)s"
            ),
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def log_source_fetch(
    *,
    source_key: str,
    url: str,
    status: str,
    retrieved_at: str,
    record_count: int | None = None,
    error: str | None = None,
    parser_warning_count: int = 0,
) -> None:
    logger = logging.getLogger("meteolens.source")
    message = (
        f"source_key={source_key} url={url} status={status} "
        f"retrieved_at={retrieved_at}"
    )
    if record_count is not None:
        message += f" record_count={record_count}"
    if parser_warning_count:
        message += f" parser_warnings={parser_warning_count}"
    if error:
        message += f" error={error}"
        logger.warning(message, extra={"request_id": "-"})
        return
    logger.info(message, extra={"request_id": "-"})


def log_api_error(*, path: str, status_code: int, code: str, message: str) -> None:
    logging.getLogger("meteolens.api").warning(
        f"path={path} status_code={status_code} code={code} message={message}",
        extra={"request_id": "-"},
    )
