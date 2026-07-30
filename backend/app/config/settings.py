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

    # CLI command for lte-discovery scanner
    # Set full path if running as systemd service where PATH may not include user bin
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
