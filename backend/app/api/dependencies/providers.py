from fastapi import Depends, Request
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.cli import CLIAdapter
from app.gps import GPSProvider, create_gps_provider
from app.config.settings import get_settings, Settings
from app.core.mission_executor import MissionExecutor


def get_cli_adapter(settings: Settings = Depends(get_settings)) -> CLIAdapter:
    return CLIAdapter(command=settings.LTE_SCAN_COMMAND)


def get_gps_provider(settings: Settings = Depends(get_settings)) -> GPSProvider:
    return create_gps_provider(provider_type=settings.GPS_PROVIDER)


def get_mission_executor(request: Request) -> MissionExecutor:
    return request.app.state.mission_executor
