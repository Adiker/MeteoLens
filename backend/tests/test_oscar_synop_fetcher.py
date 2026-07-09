import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "geometry" / "fetch_oscar_synop_stations.py"


def _load_fetcher():
    spec = importlib.util.spec_from_file_location("fetch_oscar_synop_stations", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fetch_oscar_station_rejects_non_matching_wigos(monkeypatch) -> None:
    fetcher = _load_fetcher()

    def fake_fetch_json(url: str, *, timeout: float):
        return {
            "stationSearchResults": [
                {
                    "id": 1,
                    "wigosId": "0-20000-0-99999",
                    "latitude": 53.0,
                    "longitude": 23.0,
                    "wigosStationIdentifiers": [
                        {"wigosStationIdentifier": "0-20000-0-99999"}
                    ],
                }
            ]
        }

    monkeypatch.setattr(fetcher, "_fetch_json", fake_fetch_json)

    with pytest.raises(RuntimeError, match="none contained an exact WIGOS ID match"):
        fetcher.fetch_oscar_station("0-20000-0-12295", timeout=1)


def test_fetch_oscar_station_accepts_nested_wigos_identifier(monkeypatch) -> None:
    fetcher = _load_fetcher()

    def fake_fetch_json(url: str, *, timeout: float):
        return {
            "stationSearchResults": [
                {
                    "id": 1,
                    "wigosId": "legacy-id",
                    "latitude": 53.1083333333,
                    "longitude": 23.1722222222,
                    "wigosStationIdentifiers": [
                        {"wigosStationIdentifier": "0-20000-0-12295"}
                    ],
                }
            ]
        }

    monkeypatch.setattr(fetcher, "_fetch_json", fake_fetch_json)

    station = fetcher.fetch_oscar_station("0-20000-0-12295", timeout=1)

    assert station["id"] == 1
    assert station["latitude"] == 53.1083333333
