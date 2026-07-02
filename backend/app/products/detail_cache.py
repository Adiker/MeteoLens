from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ProductDetailCacheEntry(BaseModel):
    product_id: str
    url: str
    retrieved_at: datetime
    files: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class ProductDetailCache:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir / "product_details"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, product_id: str) -> Path:
        safe_id = product_id.replace("/", "_")
        return self.cache_dir / f"{safe_id}.json"

    def write_success(
        self,
        *,
        product_id: str,
        url: str,
        retrieved_at: datetime,
        files: list[dict[str, Any]],
    ) -> None:
        payload = ProductDetailCacheEntry(
            product_id=product_id,
            url=url,
            retrieved_at=retrieved_at,
            files=files,
            error=None,
        )
        self._path_for(product_id).write_text(payload.model_dump_json(indent=2), encoding="utf-8")

    def write_error(self, *, product_id: str, url: str, error: str) -> None:
        payload = ProductDetailCacheEntry(
            product_id=product_id,
            url=url,
            retrieved_at=datetime.now(UTC),
            files=[],
            error=error,
        )
        self._path_for(product_id).write_text(payload.model_dump_json(indent=2), encoding="utf-8")

    def read(self, product_id: str) -> ProductDetailCacheEntry | None:
        cache_file = self._path_for(product_id)
        if not cache_file.exists():
            return None
        return ProductDetailCacheEntry.model_validate_json(cache_file.read_text(encoding="utf-8"))
