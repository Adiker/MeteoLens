from app.core.config import Settings, get_settings
from app.geometry.loader import reset_geometry_store


def apply_test_settings(monkeypatch, settings: Settings) -> None:
    get_settings.cache_clear()
    reset_geometry_store()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.db.engine.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.v1.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.geometry.loader.get_settings", lambda: settings)
