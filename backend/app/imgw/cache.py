from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class CacheStatus(BaseModel):
    status: str
    last_success_at: datetime | None = None
    age_seconds: int | None = None
    record_count: int | None = None
    parser_warnings: list[str] = []
    error: str | None = None


class CachedSourcePayload(BaseModel):
    source_key: str
    url: str | None = None
    retrieved_at: datetime
    raw_payload: Any = None
    normalized_payload: list[dict[str, Any]] = []
    record_count: int = 0
    parser_warnings: list[str] = []
    error: str | None = None


class SourceCache:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir

    def _path_for(self, source_key: str) -> Path:
        return self.cache_dir / f"{source_key}.json"

    def write_success(
        self,
        *,
        source_key: str,
        url: str,
        retrieved_at: datetime,
        raw_payload: Any,
        normalized_payload: list[dict[str, Any]],
        parser_warnings: list[str],
    ) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "source_key": source_key,
            "url": url,
            "retrieved_at": retrieved_at.isoformat(),
            "raw_payload": raw_payload,
            "normalized_payload": normalized_payload,
            "record_count": len(normalized_payload),
            "parser_warnings": parser_warnings,
            "error": None,
        }
        self._path_for(source_key).write_text(_json_dump(payload), encoding="utf-8")

    def write_error(self, *, source_key: str, error: str) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "source_key": source_key,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "raw_payload": None,
            "normalized_payload": [],
            "record_count": 0,
            "parser_warnings": [],
            "error": error,
        }
        self._path_for(source_key).write_text(_json_dump(payload), encoding="utf-8")

    def read(self, source_key: str) -> CachedSourcePayload | None:
        cache_file = self._path_for(source_key)
        if not cache_file.exists():
            return None

        return CachedSourcePayload.model_validate(_json_load(cache_file))

    def status(self, source_key: str, *, ttl_seconds: int) -> CacheStatus:
        cache_file = self._path_for(source_key)
        if not cache_file.exists():
            return CacheStatus(status="empty")

        try:
            payload = _json_load(cache_file)
            retrieved_at = datetime.fromisoformat(payload["retrieved_at"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return CacheStatus(status="invalid", error=str(exc))

        age = max(0, round((datetime.now(UTC) - retrieved_at).total_seconds()))
        status = "fresh" if age <= ttl_seconds and not payload.get("error") else "stale"
        if payload.get("error"):
            status = "error"

        return CacheStatus(
            status=status,
            last_success_at=None if payload.get("error") else retrieved_at,
            age_seconds=age,
            record_count=payload.get("record_count"),
            parser_warnings=payload.get("parser_warnings", []),
            error=payload.get("error"),
        )


def _json_dump(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _json_load(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))
