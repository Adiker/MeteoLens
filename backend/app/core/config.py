from functools import lru_cache
from pathlib import Path

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="METEOLENS_", env_file="../.env", extra="ignore")

    env: str = "development"
    service_name: str = "meteolens-backend"
    version: str = "0.1.0"
    imgw_base_url: AnyUrl = "https://danepubliczne.imgw.pl"
    frontend_origin: str = "http://localhost:5173"
    database_url: str = "sqlite:///../data/meteolens.sqlite3"
    cache_dir: Path = Path("../data/cache")
    geometry_dir: Path = Path("../data/geometry")
    log_level: str = "INFO"
    sync_on_startup: bool = False
    refresh_synop_seconds: int = Field(default=600, ge=60)
    refresh_hydro_seconds: int = Field(default=600, ge=60)
    refresh_meteo_seconds: int = Field(default=600, ge=60)
    refresh_warnings_seconds: int = Field(default=300, ge=60)
    product_detail_cache_seconds: int = Field(default=3600, ge=300)
    product_file_retention_hours: int = Field(default=24, ge=1)
    product_max_cached_files: int = Field(default=500, ge=10)
    observation_retention_days: int = Field(default=30, ge=1)
    imgw_timeout_seconds: float = Field(default=20.0, gt=0)
    imgw_max_retries: int = Field(default=2, ge=0)
    imgw_retry_delay_seconds: float = Field(default=0.25, ge=0)

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
