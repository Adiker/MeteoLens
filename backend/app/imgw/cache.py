import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from pydantic import BaseModel, Field


class CacheStatus(BaseModel):
    status: str
    last_success_at: datetime | None = None
    age_seconds: int | None = None
    record_count: int | None = None
    parser_warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class CachedSourcePayload(BaseModel):
    source_key: str
    url: str | None = None
    retrieved_at: datetime
    raw_payload: Any = None
    normalized_payload: list[dict[str, Any]] = Field(default_factory=list)
    record_count: int = 0
    parser_warnings: list[str] = Field(default_factory=list)
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
        write_text_atomic(self._path_for(source_key), _json_dump(payload))

    def write_error(self, *, source_key: str, error: str) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self._path_for(source_key)
        payload = _load_existing_success(cache_file)
        if payload is not None:
            payload["error"] = error
            payload["last_error_at"] = datetime.now(UTC).isoformat()
            write_text_atomic(cache_file, _json_dump(payload))
            return

        payload = {
            "source_key": source_key,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "raw_payload": None,
            "normalized_payload": [],
            "record_count": 0,
            "parser_warnings": [],
            "error": error,
        }
        write_text_atomic(self._path_for(source_key), _json_dump(payload))

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
        has_success_payload = payload.get("raw_payload") is not None
        status = "fresh" if age <= ttl_seconds and not payload.get("error") else "stale"
        if payload.get("error"):
            status = "stale" if has_success_payload else "error"

        return CacheStatus(
            status=status,
            last_success_at=retrieved_at if has_success_payload else None,
            age_seconds=age,
            record_count=payload.get("record_count"),
            parser_warnings=payload.get("parser_warnings", []),
            error=payload.get("error"),
        )


def write_text_atomic(path: Path, text: str) -> None:
    # Concurrent readers (API handlers, other workers) must never see a
    # truncated file, so write to a sibling temp file and atomically replace.
    tmp = NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    try:
        with tmp:
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp.name, path)
    except BaseException:
        Path(tmp.name).unlink(missing_ok=True)
        raise


def _json_dump(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _json_load(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _load_existing_success(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = _json_load(path)
    except (OSError, ValueError, TypeError):
        return None
    if payload.get("raw_payload") is None:
        return None
    return payload
