from functools import lru_cache
from pathlib import Path

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="METEOLENS_", env_file="../.env", extra="ignore")

    env: str = "development"
    service_name: str = "meteolens-backend"
    # Keep the public API/health label aligned with the GitHub prerelease tag.
    # Packaging itself uses the PEP 440 equivalent, ``0.1.0a0``.
    version: str = "0.1.0-alpha"
    imgw_base_url: AnyUrl = "https://danepubliczne.imgw.pl"
    frontend_origin: str = "http://localhost:5173"
    admin_token: str | None = None
    database_url: str = "sqlite:///../data/meteolens.sqlite3"
    cache_dir: Path = Path("../data/cache")
    geometry_dir: Path = Path("../data/geometry")
    log_level: str = "INFO"
    log_format: str = "text"
    metrics_enabled: bool = False
    sync_on_startup: bool = False
    refresh_enabled: bool = False
    refresh_synop_seconds: int = Field(default=600, ge=60)
    refresh_hydro_seconds: int = Field(default=600, ge=60)
    refresh_meteo_seconds: int = Field(default=600, ge=60)
    refresh_warnings_seconds: int = Field(default=300, ge=60)
    product_detail_cache_seconds: int = Field(default=3600, ge=300)
    product_file_retention_hours: int = Field(default=24, ge=1)
    product_max_cached_files: int = Field(default=500, ge=10)
    product_refresh_enabled: bool = False
    product_refresh_ids: str = (
        "COSMO_HVD_00_00,COSMO_HVD_06_00,COSMO_HVD_12_00,COSMO_HVD_18_00"
    )
    product_max_detail_manifests: int = Field(default=50, ge=1)
    product_binary_max_files: int = Field(default=4, ge=1)
    product_download_timeout_seconds: float = Field(default=180.0, gt=0)
    product_file_max_mb: int = Field(default=300, ge=1)
    product_render_max_lead_hours: int = Field(default=24, ge=0)
    product_render_lead_step_hours: int = Field(default=3, ge=1)
    product_render_width: int = Field(default=700, ge=100, le=2000)
    product_render_prefetch_frames: int = Field(default=0, ge=0)
    product_render_max_concurrent: int = Field(default=1, ge=1, le=4)
    observation_retention_days: int = Field(default=30, ge=1)
    archive_backfill_max_days: int = Field(default=31, ge=1, le=366)
    archive_backfill_max_files: int = Field(default=12, ge=1, le=500)
    archive_backfill_rate_limit_seconds: float = Field(default=0.5, ge=0)
    archive_backfill_cooldown_seconds: int = Field(default=900, ge=0, le=86_400)
    archive_download_max_mb: int = Field(default=50, ge=1, le=500)
    archive_zip_max_entries: int = Field(default=10, ge=1, le=1000)
    archive_zip_entry_max_mb: int = Field(default=100, ge=1, le=1000)
    archive_zip_total_uncompressed_max_mb: int = Field(default=150, ge=1, le=2000)
    archive_max_rows_per_file: int = Field(default=50_000, ge=100, le=1_000_000)
    imgw_timeout_seconds: float = Field(default=20.0, gt=0)
    imgw_max_retries: int = Field(default=2, ge=0)
    imgw_retry_delay_seconds: float = Field(default=0.25, ge=0)

    @property
    def frontend_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]
        # A direct production backend must not accidentally grant browser access
        # to a development or wildcard origin. Same-origin nginx traffic does not
        # require CORS at all, so an empty list is the safe default.
        if self.env.lower() in {"production", "prod"}:
            return [
                origin
                for origin in origins
                if origin.startswith("https://")
            ]
        return [origin for origin in origins if origin != "*"]

    @property
    def admin_operations_enabled(self) -> bool:
        """Whether administrative HTTP operations are deliberately enabled."""
        return bool(self.admin_token)

    @property
    def product_refresh_id_list(self) -> list[str]:
        return [pid.strip() for pid in self.product_refresh_ids.split(",") if pid.strip()]

    @property
    def archive_download_max_bytes(self) -> int:
        return self.archive_download_max_mb * 1024 * 1024

    @property
    def archive_zip_entry_max_bytes(self) -> int:
        return self.archive_zip_entry_max_mb * 1024 * 1024

    @property
    def archive_zip_total_uncompressed_max_bytes(self) -> int:
        return self.archive_zip_total_uncompressed_max_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
