from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.cli import CLIAdapter
from app.gps import GPSProvider
from app.services import ScanService
from app.schemas.scan import ScanRequest, ScanSessionResponse
from app.api.dependencies.providers import get_cli_adapter, get_gps_provider
from app.config.settings import get_settings

router = APIRouter(prefix="/api/v1/scan", tags=["scan"])


@router.post("", response_model=ScanSessionResponse)
def execute_scan(
    request: ScanRequest,
    db: Session = Depends(get_db),
    cli_adapter: CLIAdapter = Depends(get_cli_adapter),
    gps_provider: GPSProvider = Depends(get_gps_provider),
):
    service = ScanService(db=db, cli_adapter=cli_adapter, gps_provider=gps_provider)

    try:
        settings = get_settings()
        result = service.execute_scan(band=request.band, timeout=settings.SCAN_TIMEOUT)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
