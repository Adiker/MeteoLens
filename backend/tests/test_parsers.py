import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.imgw.parsers import parse_source
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


def test_product_parser_marks_manifest_only_products() -> None:
    result = parse_source("product", load_fixture("product"), source_metadata("product"))

    product = result.records[0]
    assert isinstance(product, ProductManifest)
    assert product.source_id == "COSMO_HVD_00_00"
    assert "GRIB" in product.description

