from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache


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

    # CLI command for lte-discovery scanner
    # Set full path if running as a systemd service where PATH may not include user bin
    CLI_COMMAND: str = "lte-discovery"

    LOG_LEVEL: str = "INFO"

    APP_ENV: str = "production"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    TIMEZONE: str = "Asia/Jakarta"

    # CORS settings - for frontend running on different machines during development
    ALLOW_ALL_ORIGINS: bool = True
    ORIGIN_WHITELIST: str = ""  # Comma-separated list of origins, e.g., http://localhost:3000,http://192.168.1.100:3000

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
