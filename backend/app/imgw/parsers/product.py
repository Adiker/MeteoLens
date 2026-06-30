from typing import Any

from app.imgw.parsers.utils import missing_fields
from app.normalization.models import ProductManifest, SourceMetadata


def parse_product_manifest(
    payload: Any,
    source: SourceMetadata,
) -> tuple[list[ProductManifest], list[str]]:
    if not isinstance(payload, list):
        return [], ["Product payload is not a list."]

    records: list[ProductManifest] = []
    warnings: list[str] = []

    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            warnings.append(f"Product row {index} is not an object.")
            continue

        source_id = str(row.get("id") or "")
        if not source_id:
            warnings.append(f"Product row {index} has no id.")
            continue

        records.append(
            ProductManifest(
                id=f"product:{source_id}",
                source_id=source_id,
                description=str(row.get("opis") or source_id),
                url=str(row.get("url") or ""),
                missing_fields=missing_fields(row, ["id", "url", "opis"]),
                source=source,
                raw=row,
            )
        )

    return records, warnings

