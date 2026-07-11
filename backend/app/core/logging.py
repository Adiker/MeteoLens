"""Structured logging helpers for production observability."""

from __future__ import annotations

import logging
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.config import Settings

_SENSITIVE_VALUE = re.compile(
    r"(?i)(authorization|cookie|token|secret|signature|x-amz-signature)=[^\s&]+"
)
_SENSITIVE_QUERY_KEYS = {
    "authorization",
    "cookie",
    "token",
    "secret",
    "signature",
    "x-amz-signature",
    "x-amz-credential",
    "x-amz-security-token",
}


def redact_log_value(value: str) -> str:
    """Remove credentials and signed URL parameters from operational logs."""
    try:
        parsed = urlsplit(value)
        if parsed.scheme and parsed.netloc:
            query = urlencode(
                [
                    (key, "[REDACTED]" if key.lower() in _SENSITIVE_QUERY_KEYS else item)
                    for key, item in parse_qsl(parsed.query, keep_blank_values=True)
                ]
            )
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
    except ValueError:
        pass
    return _SENSITIVE_VALUE.sub(r"\1=[REDACTED]", value)


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
        f"source_key={source_key} url={redact_log_value(url)} status={status} "
        f"retrieved_at={retrieved_at}"
    )
    if record_count is not None:
        message += f" record_count={record_count}"
    if parser_warning_count:
        message += f" parser_warnings={parser_warning_count}"
    if error:
        message += f" error={redact_log_value(error)}"
        logger.warning(message, extra={"request_id": "-"})
        return
    logger.info(message, extra={"request_id": "-"})


def log_api_error(*, path: str, status_code: int, code: str, message: str) -> None:
    logging.getLogger("meteolens.api").warning(
        (
            f"path={path} status_code={status_code} code={code} "
            f"message={redact_log_value(message)}"
        ),
        extra={"request_id": "-"},
    )
