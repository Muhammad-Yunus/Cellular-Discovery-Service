from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "lte_scanner"
    DATABASE_USER: str = "lte_scanner"
    DATABASE_PASSWORD: str = "engen1us"
    DATABASE_SCHEMA: str = "app"

    GPS_PROVIDER: str = "mock"
    DEFAULT_TTY: str = "/dev/ttyUSB0"
    SCAN_TIMEOUT: int = 30

    MISSION_MAX_LOCATIONS: int = Field(default=10_000, gt=0, description="Maximum number of locations allowed per mission upload")
    MISSION_DEFAULT_RADIUS_METERS: int = Field(default=20, gt=0, description="Default geofence radius (meters) when mission radius not specified")
    MISSION_POLL_INTERVAL: int = Field(default=2, gt=0, description="Seconds between GPS location checks during mission execution")
    MISSION_GPS_FAILURE_THRESHOLD: int = Field(default=10, gt=0, description="Consecutive GPS failures before mission marked as FAILED")
    MISSION_CLI_TIMEOUT: int = Field(default=30, gt=0, description="Timeout per scan CLI call in seconds")
    MISSION_START_GPS_TIMEOUT: int = Field(default=5, gt=0, description="Maximum time to wait for GPS availability at mission start")
    MISSION_LOG_SIZE: int = Field(default=200, gt=0, description="Maximum number of log entries stored per mission")

    CLI_COMMAND: str = "lte-discovery"

    LOG_LEVEL: str = "INFO"

    APP_ENV: str = "production"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    TIMEZONE: str = "Asia/Jakarta"

    ALLOW_ALL_ORIGINS: bool = True
    ORIGIN_WHITELIST: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore TEST_MANAGEMENT_ENDPOINTS dan var test-only lain
    )


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    # In test environments, use a shorter CLI timeout so end-to-end tests
    # don't sit on a 30s subprocess.run timeout per location. Production stays
    # at 30s.
    if settings.APP_ENV == "test" and "MISSION_CLI_TIMEOUT" not in os.environ:
        settings.MISSION_CLI_TIMEOUT = 20
    return settings
