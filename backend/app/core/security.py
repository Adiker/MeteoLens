"""Small security primitives for public and administrative API operations."""

from __future__ import annotations

import hmac
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Header, HTTPException

from app.core.config import get_settings

ADMIN_TOKEN_HEADER = "X-MeteoLens-Admin-Token"


def require_admin(
    x_meteolens_admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
) -> None:
    """Require the deployment-local admin token without ever logging it.

    An absent configuration disables administrative HTTP endpoints. This lets a
    public deployment fail closed instead of accidentally exposing backfills.
    """
    settings = get_settings()
    configured_token = settings.admin_token
    if not settings.admin_operations_enabled or not configured_token:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "admin_operations_disabled",
                    "message": "Administrative operations are disabled on this deployment.",
                }
            },
        )
    if not x_meteolens_admin_token or not hmac.compare_digest(
        x_meteolens_admin_token, configured_token
    ):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "admin_authentication_required",
                    "message": "A valid administrative token is required.",
                }
            },
            headers={"WWW-Authenticate": "MeteoLensAdmin"},
        )


class ExpensiveOperationGate:
    """Reject overlapping work and suppress immediate duplicate submissions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = False
        self._recent_successes: dict[str, float] = {}

    @contextmanager
    def acquire(self, *, key: str, cooldown_seconds: int) -> Iterator[None]:
        now = time.monotonic()
        with self._lock:
            self._recent_successes = {
                recent_key: completed_at
                for recent_key, completed_at in self._recent_successes.items()
                if now - completed_at < cooldown_seconds
            }
            if self._active:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": {
                            "code": "operation_in_progress",
                            "message": "An archive import is already running.",
                        }
                    },
                )
            if cooldown_seconds and key in self._recent_successes:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": {
                            "code": "duplicate_operation_limited",
                            "message": "This archive range was imported recently.",
                        }
                    },
                    headers={"Retry-After": str(cooldown_seconds)},
                )
            self._active = True
        try:
            yield
        except Exception:
            raise
        else:
            with self._lock:
                self._recent_successes[key] = time.monotonic()
        finally:
            with self._lock:
                self._active = False

    def reset(self) -> None:
        """Test-only reset for the process-local gate."""
        with self._lock:
            self._active = False
            self._recent_successes.clear()


archive_backfill_gate = ExpensiveOperationGate()
