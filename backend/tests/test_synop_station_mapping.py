import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from app.imgw.station_mapping import (
    DEFAULT_MAPPING_PATH,
    MAPPING_METHOD,
    StationMappingError,
    SynopStationMapping,
    build_mapping_dataset,
    parse_imgw_station_catalog,
)


def _catalog(*rows: tuple[str, str, str]) -> bytes:
    return "".join(
        f'"{nsp}","{name}","{code}"\n' for nsp, name, code in rows
    ).encode("cp1250")


def _dataset(catalog: bytes, current_ids: list[str]) -> dict:
    retrieved_at = datetime(2026, 7, 14, tzinfo=UTC)
    return build_mapping_dataset(
        catalog_content=catalog,
        current_synop_payload=[
            {"id_stacji": station_id, "stacja": "name-not-used"}
            for station_id in current_ids
        ],
        catalog_retrieved_at=retrieved_at,
        current_synop_retrieved_at=retrieved_at,
        catalog_last_modified="Wed, 01 Jul 2026 12:59:59 GMT",
        current_synop_last_modified=None,
        dataset_version="test-v1",
        reviewed_at="2026-07-14",
    )


def test_catalog_parser_preserves_duplicate_nsp_source_records() -> None:
    rows = parse_imgw_station_catalog(
        _catalog(
            ("252150270", "BABIMOST", "3152"),
            ("252150270", "BABIMOST", "93152"),
        )
    )

    assert [row.station_code for row in rows] == ["3152", "93152"]


def test_mapping_builder_uses_codes_and_never_station_names() -> None:
    payload = _dataset(
        _catalog(
            ("349190600", "A NAME THAT DOES NOT MATCH", "600"),
            ("111111111", "BIELSKO-BIAŁA", "99999"),
        ),
        ["12600", "12001"],
    )

    by_nsp = {entry["nsp"]: entry for entry in payload["entries"]}
    assert by_nsp["349190600"]["stable_station_id"] == "synop:12600"
    assert by_nsp["349190600"]["mapping_status"] == "mapped"
    assert payload["unmapped_catalog_nsp"] == ["111111111"]
    assert payload["unmapped_current_synop"] == [
        {
            "current_synop_id": "12001",
            "stable_station_id": "synop:12001",
            "mapping_status": "unmapped_no_archive_catalog_entry",
        }
    ]


def test_mapping_builder_rejects_ambiguous_nsp() -> None:
    with pytest.raises(StationMappingError, match="multiple current SYNOP IDs"):
        _dataset(
            _catalog(
                ("349190600", "FIRST", "600"),
                ("349190600", "SECOND", "601"),
            ),
            ["12600", "12601"],
        )


def test_mapping_loader_requires_approved_method_and_review() -> None:
    payload = _dataset(_catalog(("349190600", "BIELSKO-BIAŁA", "600")), ["12600"])
    payload["review"]["status"] = "pending"
    with pytest.raises(StationMappingError, match="approved review"):
        SynopStationMapping(payload)

    payload["review"]["status"] = "approved"
    payload["mapping_method"] = "station_name"
    with pytest.raises(StationMappingError, match="Unapproved"):
        SynopStationMapping(payload)


def test_mapping_loader_rejects_unofficial_or_inconsistent_artifact() -> None:
    payload = _dataset(_catalog(("349190600", "BIELSKO-BIAŁA", "600")), ["12600"])

    unofficial = deepcopy(payload)
    unofficial["sources"]["station_catalog"]["url"] = "https://example.test/stations.csv"
    with pytest.raises(StationMappingError, match="not official IMGW"):
        SynopStationMapping(unofficial)

    duplicate_target = deepcopy(payload)
    duplicate_target["entries"].append(
        {
            **duplicate_target["entries"][0],
            "nsp": "111111111",
        }
    )
    duplicate_target["counts"]["mapped"] = 2
    duplicate_target["counts"]["catalog_entries"] = 2
    duplicate_target["counts"]["catalog_records"] = 2
    with pytest.raises(StationMappingError, match="Multiple NSP values map"):
        SynopStationMapping(duplicate_target)

    inconsistent_counts = deepcopy(payload)
    inconsistent_counts["counts"]["mapped"] = 2
    with pytest.raises(StationMappingError, match="counts are inconsistent"):
        SynopStationMapping(inconsistent_counts)


def test_committed_mapping_is_approved_and_resolves_real_imgw_ids() -> None:
    payload = json.loads(DEFAULT_MAPPING_PATH.read_text(encoding="utf-8"))
    mapping = SynopStationMapping(payload)

    assert payload["mapping_method"] == MAPPING_METHOD
    assert payload["counts"] == {
        "catalog_records": 2176,
        "catalog_entries": 2173,
        "mapped": 61,
        "unmapped_catalog_entries": 2112,
        "unmapped_current_synop_ids": 1,
    }
    assert mapping.resolve("349190600").station_id == "synop:12600"
    unresolved = mapping.resolve("999999999")
    assert unresolved.station_id == "synop-archive:999999999"
    assert unresolved.mapping_status == "unmapped_not_in_mapping_source"
