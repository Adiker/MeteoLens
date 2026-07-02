from app.core.config import Settings


def test_frontend_origins_support_comma_separated_values() -> None:
    settings = Settings(frontend_origin="https://a.example, https://b.example")
    assert settings.frontend_origins == ["https://a.example", "https://b.example"]


def test_imgw_retry_settings_have_production_defaults() -> None:
    settings = Settings()
    assert settings.imgw_timeout_seconds == 20.0
    assert settings.imgw_max_retries == 2
    assert settings.imgw_retry_delay_seconds == 0.25
