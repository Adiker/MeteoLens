import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.imgw.parsers import parse_source
from app.imgw.parsers.utils import (
    parse_datetime,
    parse_float,
    parse_int,
    parse_synop_datetime,
)
from app.normalization.models import ProductManifest, SourceMetadata, Station, Warning

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def source_metadata(source_key: str) -> SourceMetadata:
    return SourceMetadata(
        source_key=source_key,
        url=f"https://danepubliczne.imgw.pl/api/data/{source_key}",
        retrieved_at=datetime(2026, 6, 30, 7, 30, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("source_key", "expected_count"),
    [
        ("synop", 2),
        ("hydro", 1),
        ("meteo", 1),
        ("warningsmeteo", 1),
        ("warningshydro", 1),
        ("product", 2),
    ],
)
def test_parsers_return_normalized_records(source_key: str, expected_count: int) -> None:
    result = parse_source(source_key, load_fixture(source_key), source_metadata(source_key))

    assert result.warnings == []
    assert len(result.records) == expected_count


def test_synop_parser_preserves_missing_values_and_marks_missing_geometry() -> None:
    result = parse_source("synop", load_fixture("synop"), source_metadata("synop"))

    first = result.records[0]
    second = result.records[1]
    assert isinstance(first, Station)
    assert first.id == "synop:12295"
    assert first.lat is None
    assert "lat" in first.missing_fields
    assert first.observations[0].metric == "temperature"
    assert first.observations[0].value == 24.3
    assert isinstance(second, Station)
    assert "cisnienie" in second.missing_fields
    assert any(observation.missing for observation in second.observations)


def test_hydro_parser_uses_per_metric_timestamps() -> None:
    result = parse_source("hydro", load_fixture("hydro"), source_metadata("hydro"))

    station = result.records[0]
    assert isinstance(station, Station)
    assert station.lat == 51.5253
    assert station.lon == 14.8217
    water_level = next(item for item in station.observations if item.metric == "water_level")
    flow = next(item for item in station.observations if item.metric == "flow")
    assert water_level.observed_at is not None
    assert flow.observed_at is not None
    assert water_level.observed_at != flow.observed_at


def test_hydro_parser_reports_missing_per_metric_timestamps() -> None:
    payload = load_fixture("hydro")
    payload[0]["przeplyw_data"] = None

    result = parse_source("hydro", payload, source_metadata("hydro"))

    station = result.records[0]
    assert isinstance(station, Station)
    assert "przeplyw_data" in station.missing_fields
    flow = next(item for item in station.observations if item.metric == "flow")
    assert flow.observed_at is None


def test_meteo_parser_reports_missing_per_metric_timestamps() -> None:
    payload = load_fixture("meteo")
    payload[0]["opad_10min_data"] = None

    result = parse_source("meteo", payload, source_metadata("meteo"))

    station = result.records[0]
    assert isinstance(station, Station)
    assert "opad_10min_data" in station.missing_fields
    precipitation = next(
        item for item in station.observations if item.metric == "precipitation_10min"
    )
    assert precipitation.observed_at is None


def test_warnings_parsers_keep_area_codes() -> None:
    meteo = parse_source(
        "warningsmeteo",
        load_fixture("warningsmeteo"),
        source_metadata("warningsmeteo"),
    ).records[0]
    hydro = parse_source(
        "warningshydro",
        load_fixture("warningshydro"),
        source_metadata("warningshydro"),
    ).records[0]

    assert isinstance(meteo, Warning)
    assert meteo.level == 2
    assert [area.code for area in meteo.areas] == ["1205", "1207", "2461"]
    assert isinstance(hydro, Warning)
    assert hydro.level == -1
    assert hydro.areas[0].code == "Z_P_WP_1856"


def test_warnings_parsers_handle_null_area_lists() -> None:
    meteo_payload = load_fixture("warningsmeteo")
    hydro_payload = load_fixture("warningshydro")
    meteo_payload[0]["teryt"] = None
    hydro_payload[0]["obszary"] = None

    meteo = parse_source(
        "warningsmeteo",
        meteo_payload,
        source_metadata("warningsmeteo"),
    )
    hydro = parse_source(
        "warningshydro",
        hydro_payload,
        source_metadata("warningshydro"),
    )

    assert meteo.warnings == []
    assert hydro.warnings == []
    assert isinstance(meteo.records[0], Warning)
    assert isinstance(hydro.records[0], Warning)
    assert meteo.records[0].areas == []
    assert hydro.records[0].areas == []
    assert "teryt" in meteo.records[0].missing_fields
    assert "obszary" in hydro.records[0].missing_fields


def test_warnings_parsers_warn_on_invalid_area_lists() -> None:
    meteo_payload = load_fixture("warningsmeteo")
    hydro_payload = load_fixture("warningshydro")
    meteo_payload[0]["teryt"] = "1205"
    hydro_payload[0]["obszary"] = {"wojewodztwo": "śląskie"}

    meteo = parse_source(
        "warningsmeteo",
        meteo_payload,
        source_metadata("warningsmeteo"),
    )
    hydro = parse_source(
        "warningshydro",
        hydro_payload,
        source_metadata("warningshydro"),
    )

    assert meteo.records[0].areas == []
    assert hydro.records[0].areas == []
    assert meteo.warnings == ["Meteo warning row 0 field 'teryt' is not a list."]
    assert hydro.warnings == ["Hydro warning row 0 field 'obszary' is not a list."]


def test_product_parser_marks_manifest_only_products() -> None:
    result = parse_source("product", load_fixture("product"), source_metadata("product"))

    product = result.records[0]
    assert isinstance(product, ProductManifest)
    assert product.source_id == "COSMO_HVD_00_00"
    assert "GRIB" in product.description


def test_synop_parser_keeps_a_real_zero_distinct_from_missing() -> None:
    # suma_opadu ("0") is a genuine zero measurement, not a missing value —
    # it must parse to 0.0 and must NOT be listed in missing_fields, the
    # mirror image of the "never turn null into 0" rule.
    result = parse_source("synop", load_fixture("synop"), source_metadata("synop"))

    first = result.records[0]
    assert isinstance(first, Station)
    precipitation = next(obs for obs in first.observations if obs.metric == "precipitation_sum")
    assert precipitation.value == 0.0
    assert precipitation.missing is False
    assert "suma_opadu" not in first.missing_fields


def test_unknown_source_key_returns_no_parser_warning() -> None:
    result = parse_source("unknown", [], source_metadata("unknown"))

    assert result.records == []
    assert result.warnings == ["No parser registered for source 'unknown'."]


@pytest.mark.parametrize(
    "source_key",
    ["synop", "hydro", "meteo", "warningsmeteo", "warningshydro", "product"],
)
def test_parsers_report_non_list_payload(source_key: str) -> None:
    result = parse_source(source_key, {"not": "a list"}, source_metadata(source_key))

    assert result.records == []
    assert len(result.warnings) == 1
    assert "not a list" in result.warnings[0]


@pytest.mark.parametrize(
    "source_key",
    ["synop", "hydro", "meteo", "warningsmeteo", "warningshydro", "product"],
)
def test_parsers_skip_non_object_rows(source_key: str) -> None:
    result = parse_source(source_key, ["not-an-object"], source_metadata(source_key))

    assert result.records == []
    assert "not an object" in result.warnings[0]


@pytest.mark.parametrize(
    ("source_key", "id_field"),
    [
        ("synop", "id_stacji"),
        ("hydro", "id_stacji"),
        ("meteo", "kod_stacji"),
        ("warningsmeteo", "id"),
        ("product", "id"),
    ],
)
def test_parsers_skip_rows_missing_identifier(source_key: str, id_field: str) -> None:
    result = parse_source(source_key, [{id_field: None}], source_metadata(source_key))

    assert result.records == []
    assert "has no" in result.warnings[0]


def test_hydro_warning_uses_row_index_when_numer_missing() -> None:
    result = parse_source(
        "warningshydro",
        [{"numer": None, "zdarzenie": "Wezbranie"}],
        source_metadata("warningshydro"),
    )

    assert len(result.records) == 1
    assert result.records[0].id == "warningshydro:row-0"


def test_hydro_warning_falls_back_to_province_area_without_basin_codes() -> None:
    result = parse_source(
        "warningshydro",
        [
            {
                "numer": "1",
                "zdarzenie": "Wezbranie",
                "obszary": [
                    {"wojewodztwo": "śląskie", "opis": "zlewnia górna", "kod_zlewni": None}
                ],
            }
        ],
        source_metadata("warningshydro"),
    )

    warning = result.records[0]
    assert isinstance(warning, Warning)
    assert len(warning.areas) == 1
    assert warning.areas[0].area_type == "province"
    assert warning.areas[0].code == "śląskie"
    assert warning.areas[0].label == "zlewnia górna"


def test_hydro_warning_skips_non_object_area_entries() -> None:
    result = parse_source(
        "warningshydro",
        [{"numer": "1", "zdarzenie": "Wezbranie", "obszary": ["not-an-object"]}],
        source_metadata("warningshydro"),
    )

    assert result.records[0].areas == []
    assert "obszary item 0 is not an object" in result.warnings[0]


def test_parse_float_returns_none_for_unparseable_values() -> None:
    assert parse_float("not-a-number") is None
    assert parse_float(None) is None
    assert parse_float("") is None
    assert parse_float("12,5") == 12.5


def test_parse_int_returns_none_for_unparseable_values() -> None:
    assert parse_int("not-a-number") is None
    assert parse_int("42") == 42


def test_parse_datetime_returns_none_for_unrecognized_format() -> None:
    assert parse_datetime("not-a-date") is None
    assert parse_datetime(None) is None
    assert parse_datetime("2026-06-30T05:00:00") is not None


def test_parse_synop_datetime_returns_none_for_invalid_inputs() -> None:
    assert parse_synop_datetime(None, "5") is None
    assert parse_synop_datetime("2026-06-30", None) is None
    assert parse_synop_datetime("not-a-date", "5") is None
    assert parse_synop_datetime("2026-06-30", "not-an-hour") is None
