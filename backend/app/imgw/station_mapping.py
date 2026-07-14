"""Reviewed mapping between IMGW archive NSP and current SYNOP identifiers."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

IMGW_STATION_CATALOG_URL = (
    "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/"
    "dane_meteorologiczne/wykaz_stacji.csv"
)
IMGW_CURRENT_SYNOP_URL = "https://danepubliczne.imgw.pl/api/data/synop"
MAPPING_METHOD = "imgw_station_code_wmo_block_12_exact_current_id"
DEFAULT_MAPPING_PATH = Path(__file__).parent / "data" / "synop_station_mapping.v1.json"


class StationMappingError(RuntimeError):
    """Raised when a reviewed mapping artifact is missing or invalid."""


@dataclass(frozen=True)
class StationResolution:
    station_id: str
    source_station_id: str
    mapping_status: str
    mapping_version: str
    mapping_source_url: str
    mapping_retrieved_at: datetime


@dataclass(frozen=True)
class _CatalogRow:
    nsp: str
    station_name: str
    station_code: str


def parse_imgw_station_catalog(content: bytes) -> list[_CatalogRow]:
    """Parse the official three-column IMGW station catalogue."""
    try:
        text = content.decode("cp1250")
    except UnicodeDecodeError as exc:
        raise StationMappingError("IMGW station catalogue is not valid CP1250.") from exc

    rows: list[_CatalogRow] = []
    for line_number, values in enumerate(csv.reader(StringIO(text)), start=1):
        if len(values) != 3:
            raise StationMappingError(
                f"IMGW station catalogue line {line_number} has {len(values)} columns."
            )
        nsp, station_name, station_code = (value.strip() for value in values)
        if not re.fullmatch(r"\d{9}", nsp):
            raise StationMappingError(
                f"IMGW station catalogue line {line_number} has invalid NSP {nsp!r}."
            )
        if not station_name or not station_code:
            raise StationMappingError(
                f"IMGW station catalogue line {line_number} has an empty field."
            )
        rows.append(_CatalogRow(nsp, station_name, station_code))
    if not rows:
        raise StationMappingError("IMGW station catalogue is empty.")
    return rows


def parse_current_synop_ids(payload: Any) -> set[str]:
    """Validate and extract stable IDs from the current IMGW SYNOP endpoint."""
    if not isinstance(payload, list) or not payload:
        raise StationMappingError("Current IMGW SYNOP payload is not a non-empty list.")
    ids: set[str] = set()
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise StationMappingError(f"Current IMGW SYNOP row {index} is not an object.")
        station_id = str(row.get("id_stacji") or "").strip()
        if not re.fullmatch(r"12\d{3}", station_id):
            raise StationMappingError(
                f"Current IMGW SYNOP row {index} has a non-block-12 id_stacji."
            )
        if station_id in ids:
            raise StationMappingError(f"Duplicate current IMGW SYNOP ID: {station_id}.")
        ids.add(station_id)
    return ids


def build_mapping_dataset(
    *,
    catalog_content: bytes,
    current_synop_payload: Any,
    catalog_retrieved_at: datetime,
    current_synop_retrieved_at: datetime,
    catalog_last_modified: str | None,
    current_synop_last_modified: str | None,
    dataset_version: str,
    reviewed_at: str,
) -> dict[str, Any]:
    """Build a source-key-only mapping; station names never participate."""
    catalog_rows = parse_imgw_station_catalog(catalog_content)
    current_ids = parse_current_synop_ids(current_synop_payload)
    mapped_current_ids: set[str] = set()
    entries: list[dict[str, Any]] = []
    unmapped_catalog_nsp: list[str] = []

    rows_by_nsp: dict[str, list[_CatalogRow]] = {}
    for row in catalog_rows:
        rows_by_nsp.setdefault(row.nsp, []).append(row)

    for nsp, source_rows in sorted(rows_by_nsp.items()):
        candidates = {
            f"12{int(row.station_code):03d}"
            for row in source_rows
            if re.fullmatch(r"\d{1,3}", row.station_code)
            and f"12{int(row.station_code):03d}" in current_ids
        }
        if len(candidates) > 1:
            raise StationMappingError(
                f"NSP {nsp} resolves to multiple current SYNOP IDs: "
                f"{', '.join(sorted(candidates))}."
            )
        if candidates:
            candidate = next(iter(candidates))
            if candidate in mapped_current_ids:
                raise StationMappingError(
                    f"Multiple NSP values resolve to current SYNOP ID {candidate}."
                )
            mapped_current_ids.add(candidate)
            mapping_status = "mapped"
            stable_station_id = f"synop:{candidate}"
            current_synop_id = candidate
        else:
            unmapped_catalog_nsp.append(nsp)
            continue
        entries.append(
            {
                "nsp": nsp,
                "archive_station_names": sorted(
                    {row.station_name for row in source_rows}
                ),
                "imgw_station_codes": sorted(
                    {row.station_code for row in source_rows}
                ),
                "current_synop_id": current_synop_id,
                "stable_station_id": stable_station_id,
                "mapping_status": mapping_status,
            }
        )

    current_bytes = json.dumps(
        current_synop_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        "format_version": 1,
        "dataset_version": dataset_version,
        "provider": "IMGW-PIB",
        "attribution": "Źródło identyfikatorów stacji: IMGW-PIB; przetworzenie: MeteoLens.",
        "terms_url": "https://danepubliczne.imgw.pl/pl/regulations",
        "legal_note": (
            "The mapping is a processed derivative of the same public IMGW-PIB "
            "station catalogue and current SYNOP service already reviewed for "
            "MeteoLens. It introduces no unofficial data provider and must retain "
            "IMGW-PIB attribution and the MeteoLens processed-data notice."
        ),
        "mapping_method": MAPPING_METHOD,
        "mapping_rule": (
            "Use the official IMGW catalogue station code only when it has at most "
            "three digits; prepend the documented Polish WMO block 12 and require "
            "an exact id_stacji in the fetched current IMGW SYNOP payload. Names are "
            "retained for provenance but never compared."
        ),
        "sources": {
            "station_catalog": {
                "url": IMGW_STATION_CATALOG_URL,
                "retrieved_at": catalog_retrieved_at.isoformat(),
                "last_modified": catalog_last_modified,
                "sha256": hashlib.sha256(catalog_content).hexdigest(),
                "encoding": "CP1250",
            },
            "current_synop": {
                "url": IMGW_CURRENT_SYNOP_URL,
                "retrieved_at": current_synop_retrieved_at.isoformat(),
                "last_modified": current_synop_last_modified,
                "sha256_canonical_json": hashlib.sha256(current_bytes).hexdigest(),
            },
        },
        "review": {
            "status": "approved",
            "reviewed_at": reviewed_at,
            "reviewed_by": "MeteoLens Stage 21 source/legal review",
            "notes": (
                "Both mapping inputs are official public IMGW-PIB sources. The WMO "
                "block-12 interpretation is independently checked by the reviewed "
                "OSCAR/Surface WIGOS dataset already bundled by Stage 18."
            ),
        },
        "counts": {
            "catalog_records": len(catalog_rows),
            "catalog_entries": len(rows_by_nsp),
            "mapped": len(mapped_current_ids),
            "unmapped_catalog_entries": len(unmapped_catalog_nsp),
            "unmapped_current_synop_ids": len(current_ids - mapped_current_ids),
        },
        "unmapped_catalog_nsp": unmapped_catalog_nsp,
        "unmapped_current_synop": [
            {
                "current_synop_id": station_id,
                "stable_station_id": f"synop:{station_id}",
                "mapping_status": "unmapped_no_archive_catalog_entry",
            }
            for station_id in sorted(current_ids - mapped_current_ids)
        ],
        "entries": sorted(entries, key=lambda entry: entry["nsp"]),
    }


class SynopStationMapping:
    """Validated, approved mapping used by the archive parser."""

    def __init__(self, payload: dict[str, Any]) -> None:
        if payload.get("format_version") != 1:
            raise StationMappingError("Unsupported SYNOP station mapping format.")
        if payload.get("mapping_method") != MAPPING_METHOD:
            raise StationMappingError("Unapproved SYNOP station mapping method.")
        review = payload.get("review")
        if not isinstance(review, dict) or review.get("status") != "approved":
            raise StationMappingError("SYNOP station mapping has no approved review.")
        version = payload.get("dataset_version")
        sources = payload.get("sources")
        entries = payload.get("entries")
        unmapped_catalog_nsp = payload.get("unmapped_catalog_nsp")
        if not isinstance(version, str) or not version:
            raise StationMappingError("SYNOP station mapping has no dataset version.")
        if (
            not isinstance(sources, dict)
            or not isinstance(entries, list)
            or not isinstance(unmapped_catalog_nsp, list)
        ):
            raise StationMappingError("SYNOP station mapping structure is invalid.")
        catalog = sources.get("station_catalog")
        current_synop = sources.get("current_synop")
        if not isinstance(catalog, dict) or not isinstance(current_synop, dict):
            raise StationMappingError("SYNOP station mapping has incomplete provenance.")
        try:
            retrieved_at = datetime.fromisoformat(str(catalog["retrieved_at"]))
            source_url = str(catalog["url"])
            current_retrieved_at = datetime.fromisoformat(
                str(current_synop["retrieved_at"])
            )
            current_source_url = str(current_synop["url"])
        except (KeyError, ValueError) as exc:
            raise StationMappingError("Invalid station mapping provenance.") from exc
        if source_url != IMGW_STATION_CATALOG_URL:
            raise StationMappingError("Station catalogue provenance is not official IMGW.")
        if current_source_url != IMGW_CURRENT_SYNOP_URL:
            raise StationMappingError("Current SYNOP provenance is not official IMGW.")
        if retrieved_at.utcoffset() is None or current_retrieved_at.utcoffset() is None:
            raise StationMappingError("Station mapping retrieval time has no timezone.")
        if catalog.get("encoding") != "CP1250":
            raise StationMappingError("Station catalogue provenance has invalid encoding.")
        if not re.fullmatch(r"[0-9a-f]{64}", str(catalog.get("sha256") or "")):
            raise StationMappingError("Station catalogue provenance has invalid SHA-256.")
        if not re.fullmatch(
            r"[0-9a-f]{64}", str(current_synop.get("sha256_canonical_json") or "")
        ):
            raise StationMappingError("Current SYNOP provenance has invalid SHA-256.")

        by_nsp: dict[str, dict[str, Any]] = {}
        mapped_current_ids: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise StationMappingError("SYNOP station mapping entry is not an object.")
            nsp = str(entry.get("nsp") or "")
            status = entry.get("mapping_status")
            stable_id = entry.get("stable_station_id")
            if not re.fullmatch(r"\d{9}", nsp) or nsp in by_nsp:
                raise StationMappingError(f"Invalid or duplicate mapping NSP: {nsp!r}.")
            if status != "mapped":
                raise StationMappingError(f"NSP {nsp} has unsupported mapping status.")
            current_id = str(entry.get("current_synop_id") or "")
            if not re.fullmatch(r"12\d{3}", current_id):
                raise StationMappingError(f"Mapped NSP {nsp} has invalid current ID.")
            if current_id in mapped_current_ids:
                raise StationMappingError(
                    f"Multiple NSP values map to current SYNOP ID {current_id}."
                )
            if stable_id != f"synop:{current_id}":
                raise StationMappingError(f"Mapped NSP {nsp} has invalid stable ID.")
            mapped_current_ids.add(current_id)
            by_nsp[nsp] = entry

        unmapped_nsp: set[str] = set()
        for value in unmapped_catalog_nsp:
            nsp = str(value)
            if (
                not re.fullmatch(r"\d{9}", nsp)
                or nsp in unmapped_nsp
                or nsp in by_nsp
            ):
                raise StationMappingError(f"Invalid or duplicate unmapped NSP: {nsp!r}.")
            unmapped_nsp.add(nsp)

        unmapped_current = payload.get("unmapped_current_synop")
        if not isinstance(unmapped_current, list):
            raise StationMappingError("SYNOP station mapping has no current-ID gaps.")
        unmapped_current_ids: set[str] = set()
        for entry in unmapped_current:
            if not isinstance(entry, dict):
                raise StationMappingError("Unmapped current SYNOP entry is invalid.")
            current_id = str(entry.get("current_synop_id") or "")
            if (
                not re.fullmatch(r"12\d{3}", current_id)
                or current_id in mapped_current_ids
                or current_id in unmapped_current_ids
                or entry.get("stable_station_id") != f"synop:{current_id}"
                or entry.get("mapping_status") != "unmapped_no_archive_catalog_entry"
            ):
                raise StationMappingError(
                    f"Invalid or duplicate unmapped current SYNOP ID: {current_id!r}."
                )
            unmapped_current_ids.add(current_id)

        counts = payload.get("counts")
        expected_counts = {
            "mapped": len(by_nsp),
            "unmapped_catalog_entries": len(unmapped_nsp),
            "catalog_entries": len(by_nsp) + len(unmapped_nsp),
            "unmapped_current_synop_ids": len(unmapped_current_ids),
        }
        if not isinstance(counts, dict) or any(
            counts.get(key) != value for key, value in expected_counts.items()
        ):
            raise StationMappingError("SYNOP station mapping counts are inconsistent.")
        catalog_records = counts.get("catalog_records")
        if not isinstance(catalog_records, int) or catalog_records < len(by_nsp) + len(
            unmapped_nsp
        ):
            raise StationMappingError("SYNOP station catalogue record count is invalid.")

        self.version = version
        self.source_url = source_url
        self.retrieved_at = retrieved_at
        self._by_nsp = by_nsp
        self._unmapped_nsp = unmapped_nsp

    @classmethod
    def load(cls, path: Path = DEFAULT_MAPPING_PATH) -> SynopStationMapping:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StationMappingError(f"Cannot load reviewed station mapping: {path}.") from exc
        if not isinstance(payload, dict):
            raise StationMappingError("SYNOP station mapping root is not an object.")
        return cls(payload)

    def resolve(self, nsp: str) -> StationResolution:
        entry = self._by_nsp.get(nsp)
        if entry is not None:
            station_id = str(entry["stable_station_id"])
            status = str(entry["mapping_status"])
        elif nsp in self._unmapped_nsp:
            station_id = f"synop-archive:{nsp}"
            status = "unmapped_not_current_synop"
        else:
            station_id = f"synop-archive:{nsp}"
            status = "unmapped_not_in_mapping_source"
        return StationResolution(
            station_id=station_id,
            source_station_id=nsp,
            mapping_status=status,
            mapping_version=self.version,
            mapping_source_url=self.source_url,
            mapping_retrieved_at=self.retrieved_at,
        )
