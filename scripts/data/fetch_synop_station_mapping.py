#!/usr/bin/env python3
"""Build the reviewed IMGW archive NSP to current SYNOP mapping artifact."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.imgw.station_mapping import (  # noqa: E402
    IMGW_CURRENT_SYNOP_URL,
    IMGW_STATION_CATALOG_URL,
    build_mapping_dataset,
)


def _fetch(url: str, timeout: float) -> tuple[bytes, datetime, str | None]:
    request = Request(  # noqa: S310 - fixed reviewed HTTPS sources only.
        url,
        headers={"User-Agent": "MeteoLens/0.1 (+https://github.com/Adiker/MeteoLens)"},
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read(), datetime.now(UTC), response.headers.get("Last-Modified")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=(
            REPO_ROOT
            / "backend/app/imgw/data/synop_station_mapping.v1.json"
        ),
    )
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    catalog, catalog_at, catalog_modified = _fetch(
        IMGW_STATION_CATALOG_URL, args.timeout
    )
    current_raw, current_at, current_modified = _fetch(
        IMGW_CURRENT_SYNOP_URL, args.timeout
    )
    current_payload = json.loads(current_raw.decode("utf-8"))
    dataset = build_mapping_dataset(
        catalog_content=catalog,
        current_synop_payload=current_payload,
        catalog_retrieved_at=catalog_at,
        current_synop_retrieved_at=current_at,
        catalog_last_modified=catalog_modified,
        current_synop_last_modified=current_modified,
        dataset_version=args.dataset_version,
        reviewed_at=args.reviewed_at,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    counts = dataset["counts"]
    print(
        f"wrote {args.out}: {counts['mapped']} mapped, "
        f"{counts['unmapped_catalog_entries']} catalogue entries unmapped, "
        f"{counts['unmapped_current_synop_ids']} current IDs unmapped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
