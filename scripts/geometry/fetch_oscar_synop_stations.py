#!/usr/bin/env python3
"""Fetch reviewed synop station coordinates from WMO OSCAR/Surface.

The IMGW current SYNOP endpoint does not publish coordinates. This script uses
the live IMGW station list only to discover current station IDs, then resolves
each station through the public OSCAR/Surface search API using WIGOS IDs of the
form ``0-20000-0-<IMGW id_stacji>``.

The output is a GeoJSON FeatureCollection suitable for:

    cd backend
    python -m app.geometry.import_cli import synop_stations \
      ../out/synop_stations.geojson \
      --metadata ../docs/geometry/metadata/synop_stations.json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

IMGW_SYNOP_URL = "https://danepubliczne.imgw.pl/api/data/synop"
OSCAR_SEARCH_URL = "https://oscar.wmo.int/surface/rest/api/search/station"
WIGOS_PREFIX = "0-20000-0-"


def _fetch_json(url: str, *, timeout: float) -> Any:
    with urlopen(url, timeout=timeout) as response:  # noqa: S310 - reviewed public HTTPS URLs.
        return json.load(response)


def _station_url(wigos_id: str) -> str:
    return f"{OSCAR_SEARCH_URL}?{urlencode({'wigosId': wigos_id})}"


def fetch_synop_rows(timeout: float) -> list[dict[str, Any]]:
    payload = _fetch_json(IMGW_SYNOP_URL, timeout=timeout)
    if not isinstance(payload, list):
        raise RuntimeError("IMGW synop response is not a JSON list.")
    rows = [row for row in payload if isinstance(row, dict) and row.get("id_stacji")]
    if not rows:
        raise RuntimeError("IMGW synop response did not contain station IDs.")
    return sorted(rows, key=lambda row: str(row["id_stacji"]))


def fetch_oscar_station(wigos_id: str, timeout: float) -> dict[str, Any]:
    payload = _fetch_json(_station_url(wigos_id), timeout=timeout)
    items = payload.get("stationSearchResults") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        raise RuntimeError(f"OSCAR/Surface returned no station for {wigos_id}.")
    primary = next(
        (
            item
            for item in items
            if item.get("wigosId") == wigos_id
            or any(
                identifier.get("wigosStationIdentifier") == wigos_id
                for identifier in item.get("wigosStationIdentifiers", [])
                if isinstance(identifier, dict)
            )
        ),
        items[0],
    )
    lat = primary.get("latitude")
    lon = primary.get("longitude")
    if not isinstance(lat, int | float) or not isinstance(lon, int | float):
        raise RuntimeError(f"OSCAR/Surface station {wigos_id} has no numeric coordinates.")
    return primary


def build_feature(imgw_row: dict[str, Any], oscar_station: dict[str, Any]) -> dict[str, Any]:
    code = str(imgw_row["id_stacji"])
    wigos_id = f"{WIGOS_PREFIX}{code}"
    return {
        "type": "Feature",
        "properties": {
            "code": code,
            "name": imgw_row.get("stacja") or oscar_station.get("name") or code,
            "wigos_id": wigos_id,
            "oscar_station_id": oscar_station.get("id"),
            "oscar_name": oscar_station.get("name"),
            "territory": oscar_station.get("territory"),
            "declared_status": oscar_station.get("declaredStatus"),
            "assessed_status": oscar_station.get("assessedStatus"),
            "station_type": oscar_station.get("stationTypeName"),
            "elevation_m": oscar_station.get("elevation"),
            "hp_m": oscar_station.get("hp"),
            "date_established": oscar_station.get("dateEstablished"),
        },
        "geometry": {
            "type": "Point",
            "coordinates": [
                round(float(oscar_station["longitude"]), 10),
                round(float(oscar_station["latitude"]), 10),
            ],
        },
    }


def build_collection(*, timeout: float, delay_seconds: float) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    missing: list[str] = []
    for row in fetch_synop_rows(timeout):
        code = str(row["id_stacji"])
        wigos_id = f"{WIGOS_PREFIX}{code}"
        try:
            station = fetch_oscar_station(wigos_id, timeout)
        except Exception as exc:  # noqa: BLE001 - collect all unresolved stations for one report.
            missing.append(f"{code} ({row.get('stacja')}): {exc}")
        else:
            features.append(build_feature(row, station))
        if delay_seconds:
            time.sleep(delay_seconds)

    if missing:
        raise RuntimeError("Unresolved OSCAR stations:\n" + "\n".join(missing))

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "source": "WMO OSCAR/Surface public search API",
            "imgw_station_source": IMGW_SYNOP_URL,
            "oscar_search_url": OSCAR_SEARCH_URL,
            "wigos_id_pattern": f"{WIGOS_PREFIX}<id_stacji>",
            "feature_count": len(features),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Output GeoJSON path.")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.1,
        help="Small delay between OSCAR requests to avoid bursty refreshes.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    collection = build_collection(timeout=args.timeout, delay_seconds=args.delay_seconds)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(collection, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(collection['features'])} synop station features to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
