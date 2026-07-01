import pytest

from app.geometry.loader import reset_geometry_store


@pytest.fixture(autouse=True)
def _reset_geometry_store() -> None:
    reset_geometry_store()
    yield
    reset_geometry_store()
