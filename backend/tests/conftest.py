import pytest

from app.db.engine import reset_engine_cache


@pytest.fixture(autouse=True)
def _reset_db_engine_cache() -> None:
    reset_engine_cache()
    yield
    reset_engine_cache()
