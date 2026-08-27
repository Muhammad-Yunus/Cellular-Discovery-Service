from pathlib import Path
from pydantic import Field, field_validator
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

    GPS_PROVIDER: str = "cli"
    DEFAULT_GPS_TTY: str = "/dev/ttyAMA0"

    # Moving Mock GPS parameters
    MOCK_GPS_START_LAT: float = -6.150677
    MOCK_GPS_START_LON: float = 106.896652
    MOCK_GPS_WAYPOINTS: str = ""
    MOCK_GPS_LOITER_RADIUS_M: float = 20.0
    MOCK_GPS_SPEED_MS: float = 50.0
    MOCK_GPS_LOITER_LAPS: int = 3

    # GPS CLI tool parameters
    GPS_CLI_BAUD: int = 9600
    GPS_CLI_TIMEOUT: int = 60
    GPS_CLI_COUNT: int = 10
    GPS_CLI_COMMAND: str = "/home/pi/GPS/build/gps"

    SCAN_TIMEOUT: int = 90

    MISSION_MAX_LOCATIONS: int = Field(default=10_000, gt=0, description="Maximum number of locations allowed per mission upload")
    MISSION_DEFAULT_RADIUS_METERS: int = Field(default=20, gt=0, description="Default geofence radius (meters) when mission radius not specified")
    MISSION_POLL_INTERVAL: int = Field(default=2, gt=0, description="Seconds between GPS location checks during mission execution")
    MISSION_GPS_FAILURE_THRESHOLD: int = Field(default=10, gt=0, description="Consecutive GPS failures before mission marked as FAILED")
    MISSION_CLI_TIMEOUT: int = Field(default=30, gt=0, description="Timeout per scan CLI call in seconds")
    # Scan behavior when GPS is loitering around a tower
    MISSION_SCAN_INTERVAL_SEC: float = Field(default=8.0, gt=0, description="Seconds between scans during loiter at a tower (0 = scan once)")
    MISSION_SCAN_MAX_PER_TOWER: int = Field(default=100, gt=0, description="Maximum scans per tower during loiter before stopping")
    MISSION_SCAN_MIN_FOR_VISITED: int = Field(default=4, gt=0, description="Minimum scan sessions before marking location as VISITED")
    MISSION_START_GPS_TIMEOUT: int = Field(default=5, gt=0, description="Maximum time to wait for GPS availability at mission start")
    MISSION_LOG_SIZE: int = Field(default=200, gt=0, description="Maximum number of log entries stored per mission")

    # LTE Scan (RTL-SDR) configuration
    LTE_SCAN_COMMAND: str = "lte-scan"
    LTE_SCAN_BANDS: str = "8"
    LTE_SCAN_GAIN: int = 43
    LTE_SCAN_MODE: str = "balance"  # fast, balance, full

    @field_validator("LTE_SCAN_BANDS")
    @classmethod
    def parse_band_list(cls, v):
        return [int(b.strip()) for b in v.split(",") if b.strip()]

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
