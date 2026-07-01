from app.core.config import Settings, get_settings


def apply_test_settings(monkeypatch, settings: Settings) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.db.engine.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.v1.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
