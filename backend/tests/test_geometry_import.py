"""Stage 13 tests: manifest review metadata, validation, import CLI, synop coordinates."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.geometry.import_cli import main as import_cli_main
from app.geometry.loader import GeometryStore, reset_geometry_store
from app.geometry.validation import validate_dataset
from app.main import app
from tests.settings_helpers import apply_test_settings
from tests.test_frontend_api import _seed_cache

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "geometry"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _feature(code: str, *, name: str | None = None, coordinates=None, geometry_type="Polygon"):
    properties = {"code": code}
    if name is not None:
        properties["name"] = name
    if coordinates is None:
        coordinates = [[[18.0, 50.0], [19.0, 50.0], [19.0, 51.0], [18.0, 51.0], [18.0, 50.0]]]
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {"type": geometry_type, "coordinates": coordinates},
    }


def _collection(*features):
    return {"type": "FeatureCollection", "features": list(features)}


def _all_voivodeship_features():
    return [
        _feature(f"{value:02d}", name=f"Voivodeship {value:02d}")
        for value in range(2, 33, 2)
    ]


def _metadata(**overrides):
    metadata = {
        "title": "Test dataset",
        "provider": "Test provider",
        "canonical_url": "https://example.invalid/dataset",
        "license_url": "https://example.invalid/license",
        "license_note": "Test license.",
        "attribution": "Test attribution.",
        "public_use": True,
        "commercial_use": True,
        "redistribution_note": "Test redistribution.",
        "update_cadence": "never",
        "known_limitations": "Test limitations.",
        "dataset_version": "test-1",
        "review": {
            "status": "approved",
            "reviewed_at": "2026-07-04",
            "reviewed_by": "tests",
            "notes": "Test review.",
        },
    }
    metadata.update(overrides)
    return metadata


# --- validation ---------------------------------------------------------------


def test_validation_rejects_non_feature_collection() -> None:
    report = validate_dataset("teryt_counties", {"type": "GeometryCollection"})
    assert not report.ok
    assert "FeatureCollection" in report.issues[0]


def test_validation_rejects_wrong_geometry_type() -> None:
    payload = _collection(
        _feature("1205", name="County", geometry_type="Point", coordinates=[19.0, 50.5])
    )
    report = validate_dataset("teryt_counties", payload)
    assert any("geometry type" in issue for issue in report.issues)


def test_validation_requires_point_geometry_for_stations() -> None:
    payload = _collection(_feature("12295", name="Station"))
    report = validate_dataset("synop_stations", payload)
    assert any("geometry type" in issue for issue in report.issues)


def test_validation_rejects_coordinates_outside_poland() -> None:
    payload = _collection(
        _feature(
            "1205",
            name="County",
            coordinates=[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
        )
    )
    report = validate_dataset("teryt_counties", payload)
    assert any("outside Poland bounds" in issue for issue in report.issues)


def test_validation_rejects_missing_required_properties() -> None:
    feature = _feature("1205")
    del feature["properties"]["code"]
    report = validate_dataset("teryt_counties", _collection(feature))
    assert any("no identifier property" in issue for issue in report.issues)
    assert any("no name property" in issue for issue in report.issues)


def test_validation_rejects_duplicate_and_malformed_codes() -> None:
    payload = _collection(
        _feature("1205", name="A"),
        _feature("1205", name="B"),
        _feature("125", name="C"),
    )
    report = validate_dataset("teryt_counties", payload)
    assert any("duplicate identifier" in issue for issue in report.issues)
    assert any("does not match pattern" in issue for issue in report.issues)


def test_validation_rejects_unknown_county_prefix() -> None:
    payload = _collection(_feature("9905", name="County"))
    report = validate_dataset("teryt_counties", payload)
    assert any("not a TERYT voivodeship code" in issue for issue in report.issues)


def test_validation_strict_coverage_requires_all_voivodeships() -> None:
    partial = _collection(_feature("12", name="Voivodeship 12"))
    report = validate_dataset("teryt_voivodeships", partial, strict_coverage=True)
    assert any("Missing voivodeship codes" in issue for issue in report.issues)

    complete = _collection(*_all_voivodeship_features())
    report = validate_dataset("teryt_voivodeships", complete, strict_coverage=True)
    assert report.ok


def test_validation_rejects_open_ring() -> None:
    payload = _collection(
        _feature(
            "1205",
            name="County",
            coordinates=[[[18.0, 50.0], [19.0, 50.0], [19.0, 51.0], [18.0, 51.0]]],
        )
    )
    report = validate_dataset("teryt_counties", payload)
    assert any("not closed" in issue for issue in report.issues)


# --- import CLI ---------------------------------------------------------------


def _write(path: Path, payload) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_cli_validate_returns_nonzero_for_invalid_dataset(tmp_path) -> None:
    geojson = _write(tmp_path / "bad.geojson", {"type": "GeometryCollection"})
    assert import_cli_main(["validate", "teryt_counties", str(geojson)]) == 1


def test_cli_import_installs_dataset_and_manifest(tmp_path) -> None:
    geojson = _write(
        tmp_path / "voivodeships.geojson", _collection(*_all_voivodeship_features())
    )
    metadata = _write(tmp_path / "meta.json", _metadata())
    geometry_dir = tmp_path / "geometry"

    exit_code = import_cli_main(
        [
            "import",
            "teryt_voivodeships",
            str(geojson),
            "--metadata",
            str(metadata),
            "--geometry-dir",
            str(geometry_dir),
        ]
    )

    assert exit_code == 0
    assert (geometry_dir / "teryt_voivodeships.geojson").exists()
    manifest = json.loads((geometry_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format_version"] == 2
    entry = manifest["datasets"][0]
    assert entry["key"] == "teryt_voivodeships"
    assert entry["review"]["status"] == "approved"
    assert entry["attribution"] == "Test attribution."

    store = GeometryStore(geometry_dir)
    store.load_all()
    dataset = store.get_dataset("teryt_voivodeships")
    assert dataset is not None and dataset.loaded
    assert len(dataset.features) == 16


def test_cli_import_rejects_incomplete_metadata(tmp_path) -> None:
    geojson = _write(
        tmp_path / "voivodeships.geojson", _collection(*_all_voivodeship_features())
    )
    metadata = _metadata()
    del metadata["license_url"]
    metadata_path = _write(tmp_path / "meta.json", metadata)
    geometry_dir = tmp_path / "geometry"

    exit_code = import_cli_main(
        [
            "import",
            "teryt_voivodeships",
            str(geojson),
            "--metadata",
            str(metadata_path),
            "--geometry-dir",
            str(geometry_dir),
        ]
    )

    assert exit_code == 1
    assert not (geometry_dir / "manifest.json").exists()


def test_cli_import_rejects_invalid_dataset(tmp_path) -> None:
    geojson = _write(tmp_path / "partial.geojson", _collection(_feature("12", name="V12")))
    metadata = _write(tmp_path / "meta.json", _metadata())
    geometry_dir = tmp_path / "geometry"

    exit_code = import_cli_main(
        [
            "import",
            "teryt_voivodeships",
            str(geojson),
            "--metadata",
            str(metadata),
            "--geometry-dir",
            str(geometry_dir),
        ]
    )

    assert exit_code == 1
    assert not (geometry_dir / "teryt_voivodeships.geojson").exists()


# --- loader review enforcement -------------------------------------------------


def test_loader_rejects_unreviewed_dataset(tmp_path) -> None:
    geometry_dir = tmp_path / "geometry"
    geometry_dir.mkdir()
    _write(
        geometry_dir / "teryt_voivodeships.geojson",
        _collection(*_all_voivodeship_features()),
    )
    _write(
        geometry_dir / "manifest.json",
        {
            "format_version": 2,
            "datasets": [
                {
                    "key": "teryt_voivodeships",
                    "file": "teryt_voivodeships.geojson",
                    "title": "Legacy entry without review",
                }
            ],
        },
    )

    store = GeometryStore(geometry_dir)
    store.load_all()
    dataset = store.get_dataset("teryt_voivodeships")

    assert dataset is not None
    assert not dataset.loaded
    assert dataset.features == []
    assert "dataset_not_reviewed" in (dataset.error or "")


def test_loader_rejects_invalid_dataset_file(tmp_path) -> None:
    geometry_dir = tmp_path / "geometry"
    geometry_dir.mkdir()
    _write(
        geometry_dir / "teryt_counties.geojson",
        _collection(
            _feature(
                "1205",
                name="County",
                coordinates=[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
            )
        ),
    )
    manifest_entry = _metadata()
    manifest_entry.update({"key": "teryt_counties", "file": "teryt_counties.geojson"})
    _write(
        geometry_dir / "manifest.json",
        {"format_version": 2, "datasets": [manifest_entry]},
    )

    store = GeometryStore(geometry_dir)
    store.load_all()
    dataset = store.get_dataset("teryt_counties")

    assert dataset is not None
    assert not dataset.loaded
    assert "invalid_dataset" in (dataset.error or "")


def test_bundled_synop_station_dataset_loads() -> None:
    store = GeometryStore(PROJECT_ROOT / "data" / "geometry")
    store.load_all()

    dataset = store.get_dataset("synop_stations")

    assert dataset is not None
    assert dataset.loaded
    assert dataset.review_status == "approved"
    assert dataset.commercial_use is False
    assert len(dataset.features) == 62
    bialystok = store.find_by_code(dataset_key="synop_stations", code="12295")
    assert bialystok is not None
    assert bialystok.properties["wigos_id"] == "0-20000-0-12295"
    assert bialystok.coordinates == [23.1722222222, 53.1083333333]


# --- API review metadata and synop coordinates ---------------------------------


def _fixture_settings(tmp_path) -> Settings:
    return Settings(
        cache_dir=tmp_path,
        geometry_dir=FIXTURES_DIR,
        imgw_base_url="https://danepubliczne.imgw.pl",
    )


def _prepare(tmp_path, monkeypatch) -> None:
    reset_geometry_store()
    apply_test_settings(monkeypatch, _fixture_settings(tmp_path))


def test_geometry_datasets_endpoint_exposes_review_metadata(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)

    response = TestClient(app).get("/api/v1/geometry/datasets")

    assert response.status_code == 200
    datasets = {item["key"]: item for item in response.json()["datasets"]}
    entry = datasets["teryt_counties"]
    assert entry["review_status"] == "approved"
    assert entry["reviewed_at"] == "2026-07-04"
    assert entry["provider"] == "MeteoLens test fixture"
    assert entry["attribution"] == "MeteoLens test fixture"
    assert entry["public_use"] is True
    assert entry["known_limitations"]


def test_synop_station_coordinates_come_from_reviewed_dataset(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    _seed_cache(tmp_path, ("synop",))

    response = TestClient(app).get("/api/v1/stations?type=synop")

    assert response.status_code == 200
    stations = {station["source_id"]: station for station in response.json()["stations"]}

    reviewed = stations["12295"]
    assert reviewed["lat"] == 53.1078
    assert reviewed["lon"] == 23.1621
    assert reviewed["coordinate_source"] == "MeteoLens test fixture"
    assert "lat" not in reviewed["missing_fields"]
    assert "lon" not in reviewed["missing_fields"]

    unreviewed = stations["12550"]
    assert unreviewed["lat"] is None
    assert unreviewed["coordinate_source"] is None
    assert "lat" in unreviewed["missing_fields"]


def test_synop_map_layer_only_renders_reviewed_coordinates(monkeypatch, tmp_path) -> None:
    _prepare(tmp_path, monkeypatch)
    _seed_cache(tmp_path, ("synop",))

    response = TestClient(app).get("/api/v1/map/layers?layers=synop_stations")

    assert response.status_code == 200
    layer = response.json()["layers"][0]
    feature_ids = [feature["id"] for feature in layer["geojson"]["features"]]
    assert feature_ids == ["synop:12295"]
    missing = {item["id"]: item["reason"] for item in layer["missing_geometry"]}
    assert missing == {"synop:12550": "missing_lat_lon"}
