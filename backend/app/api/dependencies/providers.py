from fastapi import Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.cli import CLIAdapter
from app.gps import GPSProvider, create_gps_provider
from app.config.settings import get_settings, Settings


def get_cli_adapter(settings: Settings = Depends(get_settings)) -> CLIAdapter:
    return CLIAdapter(command=settings.CLI_COMMAND, mock_mode=settings.MOCK_CLI)


def get_gps_provider(settings: Settings = Depends(get_settings)) -> GPSProvider:
    return create_gps_provider(provider_type=settings.GPS_PROVIDER)
