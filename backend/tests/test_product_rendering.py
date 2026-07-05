import json
import os
import time
from types import SimpleNamespace

import httpx
import numpy as np
import pytest

from app.core.config import Settings
from app.products import grib1, rendering
from app.products.rotated_grid import (
    RotatedGridSpec,
    resample_to_mercator,
    rotated_to_true,
    true_to_rotated,
)
from tests.grib_fixtures import encode_grib1_message

COSMO_GRID = rendering.EXPECTED_COSMO_GRID


def _settings(tmp_path, **overrides) -> Settings:
    return Settings(
        cache_dir=tmp_path / "cache",
        geometry_dir=tmp_path / "geometry",
        **overrides,
    )


def _full_grid_values() -> np.ndarray:
    # A smooth 0..255 gradient across the verified COSMO grid shape.
    j = np.arange(COSMO_GRID.nj)[:, None]
    i = np.arange(COSMO_GRID.ni)[None, :]
    return ((j + i) % 256).astype(np.float64)


def _seed_binary(settings: Settings, product_id: str, filename: str, payload: bytes) -> None:
    directory = settings.cache_dir.parent / "products" / "binaries" / product_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_bytes(payload)


# ---------------------------------------------------------------------------
# GRIB1 decoding
# ---------------------------------------------------------------------------


def test_grib1_decode_returns_exact_simple_packed_values() -> None:
    values = np.arange(12, dtype=np.float64).reshape(3, 4)
    message = encode_grib1_message(values, first=(-1.0, 1.0), step=(0.5, 0.5))
    record = grib1.find_record(message, parameter=11, level_type=105, level=2)
    assert record is not None
    assert record.reference_time.isoformat() == "2026-07-04T00:00:00+00:00"
    assert record.valid_time.isoformat() == "2026-07-04T01:00:00+00:00"
    np.testing.assert_array_equal(record.values(), values)


def test_grib1_decode_normalises_north_to_south_scanning() -> None:
    values = np.arange(12, dtype=np.float64).reshape(3, 4)
    message = encode_grib1_message(values, first=(-1.0, 1.0), step=(0.5, 0.5), scan=0x00)
    record = next(grib1.iter_records(message))
    # Row 0 must be the southernmost row regardless of file scanning order.
    np.testing.assert_array_equal(record.values(), values)


def test_grib1_bitmap_marks_missing_points_as_nan() -> None:
    values = np.arange(12, dtype=np.float64).reshape(3, 4)
    bitmap = np.ones((3, 4), dtype=bool)
    bitmap[0, 0] = False
    bitmap[2, 3] = False
    message = encode_grib1_message(
        values, first=(-1.0, 1.0), step=(0.5, 0.5), bitmap=bitmap
    )
    decoded = next(grib1.iter_records(message)).values()
    assert np.isnan(decoded[0, 0])
    assert np.isnan(decoded[2, 3])
    np.testing.assert_array_equal(decoded[bitmap], values[bitmap])


def test_grib1_decimal_and_binary_scale_are_applied() -> None:
    values = (np.arange(12, dtype=np.float64).reshape(3, 4) * 4) / 10.0
    message = encode_grib1_message(
        values,
        first=(-1.0, 1.0),
        step=(0.5, 0.5),
        decimal_scale=1,
        binary_scale=2,
    )
    decoded = next(grib1.iter_records(message)).values()
    np.testing.assert_allclose(decoded, values)


def test_find_record_selects_by_parameter_and_level() -> None:
    t2m = encode_grib1_message(
        np.full((3, 4), 7.0), first=(-1.0, 1.0), step=(0.5, 0.5)
    )
    surface = encode_grib1_message(
        np.full((3, 4), 9.0),
        first=(-1.0, 1.0),
        step=(0.5, 0.5),
        parameter=11,
        level_type=1,
        level=0,
    )
    data = surface + t2m
    record = grib1.find_record(data, parameter=11, level_type=105, level=2)
    assert record is not None
    assert record.values()[0, 0] == 7.0
    assert grib1.find_record(data, parameter=61, level_type=1, level=0) is None


# ---------------------------------------------------------------------------
# Rotated grid transforms
# ---------------------------------------------------------------------------


def test_rotated_grid_known_points_and_roundtrip() -> None:
    # Rotated origin maps to (90 - pole_lat, pole_lon + 180) = (50 N, 10 E).
    lat, lon = rotated_to_true(np.array([0.0]), np.array([0.0]), pole_lat=40.0, pole_lon=-170.0)
    assert lat[0] == pytest.approx(50.0, abs=1e-9)
    assert lon[0] == pytest.approx(10.0, abs=1e-9)

    cities = np.array([[52.2297, 21.0122], [54.35, 18.65], [49.299, 19.949]])
    rlat, rlon = true_to_rotated(
        cities[:, 0], cities[:, 1], pole_lat=40.0, pole_lon=-170.0
    )
    back_lat, back_lon = rotated_to_true(rlat, rlon, pole_lat=40.0, pole_lon=-170.0)
    np.testing.assert_allclose(back_lat, cities[:, 0], atol=1e-9)
    np.testing.assert_allclose(back_lon, cities[:, 1], atol=1e-9)
    # Poland must sit inside the verified COSMO output grid.
    assert np.all(rlat > COSMO_GRID.first_lat) and np.all(rlat < COSMO_GRID.last_lat)
    assert np.all(rlon > COSMO_GRID.first_lon) and np.all(rlon < COSMO_GRID.last_lon)


def test_resample_marks_outside_footprint_as_nan() -> None:
    # Large enough that the rotated footprint curves away from its own
    # geographic bounding box, leaving transparent (NaN) corners.
    spec = RotatedGridSpec(
        pole_lat=40.0,
        pole_lon=-170.0,
        first_lat=-8.0,
        first_lon=1.0,
        dlat=0.5,
        dlon=0.5,
        ni=40,
        nj=30,
    )
    values = np.arange(1200, dtype=np.float64).reshape(30, 40)
    grid, bounds = resample_to_mercator(values, spec, width=120)
    west, south, east, north = bounds
    assert west < east and south < north
    assert np.isnan(grid).any()
    assert np.isfinite(grid).any()


# ---------------------------------------------------------------------------
# Frame renderability rules
# ---------------------------------------------------------------------------


def test_parse_lead_hours_and_constant_file_detection() -> None:
    assert rendering.parse_lead_hours("202607040000_202607040300_lfff00030000") == 3
    assert rendering.parse_lead_hours("202607040000_202607061200_lfff02120000") == 60
    assert rendering.parse_lead_hours("202607040000_202607040000_lfff00000000c") is None
    assert rendering.is_constant_file("202607040000_202607040000_lfff00000000c")
    assert not rendering.is_constant_file("202607040000_202607040000_lfff00000000")
    assert rendering.parse_lead_hours("readme.txt") is None


def test_frame_render_state_window_and_step(tmp_path) -> None:
    settings = _settings(
        tmp_path, product_render_max_lead_hours=24, product_render_lead_step_hours=3
    )
    ok = rendering.frame_render_state(
        settings, "COSMO_HVD_00_00", "202607040000_202607040300_lfff00030000"
    )
    assert ok == {"renderable": True, "reason": None}
    off_step = rendering.frame_render_state(
        settings, "COSMO_HVD_00_00", "202607040000_202607040100_lfff00010000"
    )
    assert off_step["reason"] == "lead_not_on_render_step"
    beyond = rendering.frame_render_state(
        settings, "COSMO_HVD_00_00", "202607040000_202607061200_lfff02120000"
    )
    assert beyond["reason"] == "lead_beyond_render_window"
    constant = rendering.frame_render_state(
        settings, "COSMO_HVD_00_00", "202607040000_202607040000_lfff00000000c"
    )
    assert constant["reason"] == "constant_field_file"
    other_dataset = rendering.frame_render_state(
        settings, "COSMO_HVD_00_01", "202607040000_202607040300_lfff00030000"
    )
    assert other_dataset["reason"] == "product_not_renderable"


def test_renderable_descriptor_only_for_renderable_products(tmp_path) -> None:
    settings = _settings(tmp_path)
    descriptor = rendering.renderable_descriptor(settings, "COSMO_HVD_00_00")
    assert descriptor is not None
    assert descriptor["default_variable"] == "t2m"
    west, south, east, north = descriptor["bounds"]
    assert west == pytest.approx(10.963, abs=0.01)
    assert north == pytest.approx(57.695, abs=0.01)
    assert descriptor["image_coordinates"][0] == [west, north]
    assert rendering.renderable_descriptor(settings, "COMPO_SRI.comp.sri") is None
    assert rendering.renderable_descriptor(settings, "COSMO_HVD_00_01") is None


# ---------------------------------------------------------------------------
# Rendering pipeline
# ---------------------------------------------------------------------------


def test_render_frame_produces_png_with_metadata_and_cache(tmp_path) -> None:
    settings = _settings(tmp_path)
    filename = "202607040000_202607040300_lfff00030000"
    # Kelvin values 250..300 need more than 8 bits at decimal scale 0.
    payload = encode_grib1_message(
        np.clip(_full_grid_values() + 250.0, None, 300.0),
        p1_hours=3,
        bits_per_value=16,
    )
    _seed_binary(settings, "COSMO_HVD_00_00", filename, payload)

    result = rendering.render_frame(
        settings,
        product_id="COSMO_HVD_00_00",
        filename=filename,
        url="https://example.invalid/unused",
        variable_key="t2m",
    )
    assert result.from_cache is False
    png = result.png_path.read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"iTXt" in png
    assert result.metadata["frame_time"] == "2026-07-04T03:00:00+00:00"
    assert result.metadata["run_time"] == "2026-07-04T00:00:00+00:00"
    assert result.metadata["retrieved_at"]
    assert result.metadata["attribution"]
    assert result.metadata["processed_notice"]
    # Values are Kelvin in the file and Celsius in the render metadata.
    assert result.metadata["value_min"] == pytest.approx(250.0 - 273.15, abs=0.1)
    assert result.metadata["value_max"] == pytest.approx(300.0 - 273.15, abs=0.1)

    again = rendering.render_frame(
        settings,
        product_id="COSMO_HVD_00_00",
        filename=filename,
        url="https://example.invalid/unused",
        variable_key="t2m",
    )
    assert again.from_cache is True


def test_render_frame_refuses_grid_mismatch(tmp_path) -> None:
    settings = _settings(tmp_path)
    filename = "202607040000_202607040300_lfff00030000"
    payload = encode_grib1_message(
        _full_grid_values(), p1_hours=3, south_pole=(-30.0, 10.0)
    )
    _seed_binary(settings, "COSMO_HVD_00_00", filename, payload)
    with pytest.raises(rendering.RenderError) as excinfo:
        rendering.render_frame(
            settings,
            product_id="COSMO_HVD_00_00",
            filename=filename,
            url="https://example.invalid/unused",
            variable_key="t2m",
        )
    assert excinfo.value.code == "grid_mismatch"


def test_render_frame_reports_missing_variable(tmp_path) -> None:
    settings = _settings(tmp_path)
    filename = "202607040000_202607040300_lfff00030000"
    payload = encode_grib1_message(
        _full_grid_values(), p1_hours=3, parameter=61, level_type=1, level=0
    )
    _seed_binary(settings, "COSMO_HVD_00_00", filename, payload)
    with pytest.raises(rendering.RenderError) as excinfo:
        rendering.render_frame(
            settings,
            product_id="COSMO_HVD_00_00",
            filename=filename,
            url="https://example.invalid/unused",
            variable_key="t2m",
        )
    assert excinfo.value.code == "variable_missing"


def test_render_frame_rejects_non_renderable_product_and_frame(tmp_path) -> None:
    settings = _settings(tmp_path)
    with pytest.raises(rendering.RenderError) as radar:
        rendering.render_frame(
            settings,
            product_id="COMPO_SRI.comp.sri",
            filename="2026062803300000dBR.sri",
            url="https://example.invalid/unused",
            variable_key="t2m",
        )
    assert radar.value.code == "not_renderable"
    assert radar.value.status_code == 404

    with pytest.raises(rendering.RenderError) as off_window:
        rendering.render_frame(
            settings,
            product_id="COSMO_HVD_00_00",
            filename="202607040000_202607061200_lfff02120000",
            url="https://example.invalid/unused",
            variable_key="t2m",
        )
    assert off_window.value.code == "frame_not_renderable"


def _patch_transport(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client_factory(**kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(
        rendering,
        "httpx",
        SimpleNamespace(Client=client_factory, HTTPError=httpx.HTTPError),
    )


def test_download_blocked_redirect_is_explicit(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(307, headers={"location": "https://danepubliczne.imgw.pl/datastore"})

    _patch_transport(monkeypatch, handler)
    with pytest.raises(rendering.RenderError) as excinfo:
        rendering.render_frame(
            settings,
            product_id="COSMO_HVD_00_00",
            filename="202607040000_202607040300_lfff00030000",
            url="https://danepubliczne.imgw.pl/pl/datastore/getfiledown/x",
            variable_key="t2m",
        )
    assert excinfo.value.code == "download_blocked"


def test_download_html_body_is_reported_as_missing_frame(tmp_path, monkeypatch) -> None:
    # IMGW answers HTTP 200 with an HTML page for missing files, so the GRIB
    # magic check is the missing-frame signal.
    settings = _settings(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>404 Page Not Found</html>")

    _patch_transport(monkeypatch, handler)
    with pytest.raises(rendering.RenderError) as excinfo:
        rendering.render_frame(
            settings,
            product_id="COSMO_HVD_00_00",
            filename="202607040000_202607040300_lfff00030000",
            url="https://danepubliczne.imgw.pl/pl/datastore/getfiledown/x",
            variable_key="t2m",
        )
    assert excinfo.value.code == "frame_missing"
    assert excinfo.value.status_code == 404


def test_download_size_limit_is_enforced(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path, product_file_max_mb=1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"GRIB" + b"\x00" * (2 * 1024 * 1024))

    _patch_transport(monkeypatch, handler)
    with pytest.raises(rendering.RenderError) as excinfo:
        rendering.render_frame(
            settings,
            product_id="COSMO_HVD_00_00",
            filename="202607040000_202607040300_lfff00030000",
            url="https://danepubliczne.imgw.pl/pl/datastore/getfiledown/x",
            variable_key="t2m",
        )
    assert excinfo.value.code == "file_too_large"


# ---------------------------------------------------------------------------
# Retention policy
# ---------------------------------------------------------------------------


def test_binary_retention_keeps_only_newest_files(tmp_path) -> None:
    settings = _settings(tmp_path, product_binary_max_files=2)
    directory = tmp_path / "products" / "binaries" / "COSMO_HVD_00_00"
    directory.mkdir(parents=True)
    for index in range(4):
        name = f"file{index}"
        (directory / name).write_bytes(b"GRIB")
        (directory / f"{name}.meta.json").write_text("{}", encoding="utf-8")
        stamp = time.time() - (4 - index) * 60
        os.utime(directory / name, (stamp, stamp))

    rendering._enforce_binary_retention(settings, "COSMO_HVD_00_00")

    remaining = sorted(path.name for path in directory.iterdir())
    assert remaining == ["file2", "file2.meta.json", "file3", "file3.meta.json"]


def test_render_retention_evicts_old_files_with_sidecars(tmp_path) -> None:
    settings = _settings(tmp_path, product_file_retention_hours=1)
    directory = tmp_path / "products" / "renders" / "COSMO_HVD_00_00"
    directory.mkdir(parents=True)
    fresh = directory / "fresh.t2m.png"
    fresh.write_bytes(b"\x89PNG")
    (directory / "fresh.t2m.json").write_text("{}", encoding="utf-8")
    old = directory / "old.t2m.png"
    old.write_bytes(b"\x89PNG")
    (directory / "old.t2m.json").write_text("{}", encoding="utf-8")
    stamp = time.time() - 3 * 3600
    os.utime(old, (stamp, stamp))

    rendering._enforce_render_retention(settings, "COSMO_HVD_00_00")

    remaining = sorted(path.name for path in directory.iterdir())
    assert remaining == ["fresh.t2m.json", "fresh.t2m.png"]


def test_render_writes_metadata_sidecar(tmp_path) -> None:
    settings = _settings(tmp_path, product_render_max_lead_hours=48)
    filename = "202607040000_202607060000_lfff02000000"
    payload = encode_grib1_message(_full_grid_values(), p1_hours=48)
    _seed_binary(settings, "COSMO_HVD_00_00", filename, payload)
    result = rendering.render_frame(
        settings,
        product_id="COSMO_HVD_00_00",
        filename=filename,
        url="https://example.invalid/unused",
        variable_key="t2m",
    )
    sidecar = result.png_path.with_suffix(".json")
    assert sidecar.exists()
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    assert metadata["frame_time"] == "2026-07-06T00:00:00+00:00"
    assert metadata["bounds"][0] == pytest.approx(10.963, abs=0.01)
