from fastapi.testclient import TestClient

from app.main import app


def test_sources_endpoint_lists_planned_imgw_sources() -> None:
    response = TestClient(app).get("/api/v1/sources")

    assert response.status_code == 200
    payload = response.json()
    keys = {source["key"] for source in payload["sources"]}
    assert {"synop", "hydro", "meteo", "warningsmeteo", "warningshydro", "product"} <= keys
    assert all("danepubliczne.imgw.pl" in source["url"] for source in payload["sources"])

