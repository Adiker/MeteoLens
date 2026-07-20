import json
import socket
from types import SimpleNamespace

import httpx
import numpy as np
import pytest

from app.core.config import Settings
from app.core.outbound_url import OutboundUrlError, validate_product_download_url
from app.products import rendering
from tests.grib_fixtures import encode_grib1_message

ALLOWED_BASE = "https://danepubliczne.imgw.pl"
VALID_URL = (
    "https://danepubliczne.imgw.pl/pl/d/"
    "202606300000_202606300300_lfff00030000"
)
VALID_DATASTORE_URL = "https://danepubliczne.imgw.pl/pl/datastore/getfiledown/x"
COSMO_GRID = rendering.EXPECTED_COSMO_GRID


def _full_grid_values() -> np.ndarray:
    j = np.arange(COSMO_GRID.nj)[:, None]
    i = np.arange(COSMO_GRID.ni)[None, :]
    return ((j + i) % 256).astype(np.float64)


def _settings(tmp_path) -> Settings:
    return Settings(
        cache_dir=tmp_path / "cache",
        geometry_dir=tmp_path / "geometry",
        imgw_base_url=ALLOWED_BASE,
    )


def _public_addrinfo(host: str, port: int, *_args, **_kwargs):
    if host in {"danepubliczne.imgw.pl", "evil.example.test"}:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
    raise socket.gaierror("unexpected host")


def _private_addrinfo(host: str, port: int, *_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]


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


def test_validate_accepts_imgw_pl_d_url(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)
    validate_product_download_url(VALID_URL, allowed_base_url=ALLOWED_BASE)


def test_validate_accepts_imgw_datastore_url(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)
    validate_product_download_url(VALID_DATASTORE_URL, allowed_base_url=ALLOWED_BASE)


@pytest.mark.parametrize(
    ("url", "message"),
    [
        (
            "http://danepubliczne.imgw.pl/pl/d/frame.grib",
            "must use HTTPS",
        ),
        (
            "https://evil.example.test/pl/d/frame.grib",
            "not the approved IMGW host",
        ),
        (
            "https://danepubliczne.imgw.pl/api/data/product/id/COSMO_HVD_00_00",
            "not an approved IMGW route",
        ),
        (
            "https://danepubliczne.imgw.pl/pl/d/../etc/passwd",
            "parent-directory",
        ),
        (
            "https://danepubliczne.imgw.pl:8443/pl/d/frame.grib",
            "default HTTPS port",
        ),
        (
            "https://user:pass@danepubliczne.imgw.pl/pl/d/frame.grib",
            "must not include credentials",
        ),
        (
            "https://127.0.0.1/pl/d/frame.grib",
            "not the approved IMGW host",
        ),
        (
            "https://danepubliczne.imgw.pl/pl/d/frame.grib?token=secret",
            "query parameters",
        ),
    ],
)
def test_validate_rejects_disallowed_urls(url: str, message: str, monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)
    with pytest.raises(OutboundUrlError) as excinfo:
        validate_product_download_url(url, allowed_base_url=ALLOWED_BASE)
    assert excinfo.value.code == "url_not_allowed"
    assert message in str(excinfo.value)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "192.168.1.1",
        "169.254.1.1",
        "[::1]",
        "[fe80::1]",
        "[fc00::1]",
    ],
)
def test_validate_rejects_private_and_special_ip_literals(address: str) -> None:
    url = f"https://{address}/pl/d/frame.grib"
    with pytest.raises(OutboundUrlError) as excinfo:
        validate_product_download_url(url, allowed_base_url=f"https://{address}")
    assert excinfo.value.code == "url_not_allowed"
    assert "disallowed address" in str(excinfo.value)


def test_validate_rejects_dns_rebinding_to_loopback(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _private_addrinfo)
    with pytest.raises(OutboundUrlError) as excinfo:
        validate_product_download_url(
            "https://danepubliczne.imgw.pl/pl/d/frame.grib",
            allowed_base_url=ALLOWED_BASE,
        )
    assert excinfo.value.code == "url_not_allowed"
    assert "127.0.0.1" in str(excinfo.value)


def test_download_rejects_foreign_host_without_http_request(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, content=b"GRIB")

    _patch_transport(monkeypatch, handler)
    with pytest.raises(rendering.RenderError) as excinfo:
        rendering.render_frame(
            settings,
            product_id="COSMO_HVD_00_00",
            filename="202607040000_202607040300_lfff00030000",
            url="https://evil.example.test/pl/d/frame.grib",
            variable_key="t2m",
        )
    assert excinfo.value.code == "url_not_allowed"
    assert requested == []


def test_render_rejects_disallowed_url_even_when_png_cache_exists(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)
    filename = "202607040000_202607040300_lfff00030000"
    png_path = rendering.render_cache_path(settings, "COSMO_HVD_00_00", filename, "t2m")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    png_path.with_suffix(".json").write_text(
        json.dumps({"frame_time": "2026-07-04T03:00:00+00:00"}),
        encoding="utf-8",
    )

    with pytest.raises(rendering.RenderError) as excinfo:
        rendering.render_frame(
            settings,
            product_id="COSMO_HVD_00_00",
            filename=filename,
            url="https://evil.example.test/pl/d/frame.grib",
            variable_key="t2m",
        )

    assert excinfo.value.code == "url_not_allowed"


def test_download_accepts_valid_imgw_url_and_fetches(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(socket, "getaddrinfo", _public_addrinfo)
    payload = encode_grib1_message(
        np.clip(_full_grid_values() + 250.0, None, 300.0),
        p1_hours=3,
        bits_per_value=16,
    )
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, content=payload)

    _patch_transport(monkeypatch, handler)
    result = rendering.render_frame(
        settings,
        product_id="COSMO_HVD_00_00",
        filename="202607040000_202607040300_lfff00030000",
        url=VALID_DATASTORE_URL,
        variable_key="t2m",
    )
    assert requested == [VALID_DATASTORE_URL]
    assert result.from_cache is False
    assert result.png_path.exists()
