import pytest

from app.db.engine import reset_engine_cache
from app.geometry.loader import reset_geometry_store


@pytest.fixture(autouse=True)
def _reset_db_engine_cache() -> None:
    reset_engine_cache()
    yield
    reset_engine_cache()


@pytest.fixture(autouse=True)
def _reset_geometry_store() -> None:
    reset_geometry_store()
    yield
    reset_geometry_store()
