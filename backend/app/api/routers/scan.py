from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.cli import CLIAdapter
from app.gps import GPSProvider
from app.services import ScanService
from app.schemas.scan import ScanSessionResponse
from app.api.dependencies.providers import get_cli_adapter, get_gps_provider
from app.config.settings import get_settings

router = APIRouter(prefix="/api/v1/scan", tags=["scan"])


SCAN_SESSION_EXAMPLE = {
    "id": 2200,
    "scan_time": "2026-08-28T09:40:08.748887+07:00",
    "band": "5",
    "latitude": -6.150456,
    "longitude": 106.896944,
    "mission_location_id": None,
    "altitude": None,
    "course_deg": None,
    "created_at": "2026-08-28T09:40:08.748887+07:00",
    "results": [
        {
            "id": 2119,
            "operator_name": "Hutchison 3",
            "mcc": "510",
            "mnc": "89",
            "rat": "LTE",
            "status": "Available",
            "frequency_mhz": 958.0,
            "earfcn": 3780,
            "pci": 306,
            "rsrp": -29.6,
            "rsrq": None,
            "snr": None
        }
    ]
}


@router.post(
    "",
    response_model=ScanSessionResponse,
    responses={
        200: {
            "description": "Scan berhasil dieksekusi",
            "content": {
                "application/json": {
                    "example": SCAN_SESSION_EXAMPLE
                }
            }
        }
    }
)
def execute_scan(
    db: Session = Depends(get_db),
    cli_adapter: CLIAdapter = Depends(get_cli_adapter),
    gps_provider: GPSProvider = Depends(get_gps_provider),
):
    service = ScanService(db=db, cli_adapter=cli_adapter, gps_provider=gps_provider)

    try:
        settings = get_settings()
        result = service.execute_scan(
            bands=settings.LTE_SCAN_BANDS,
            timeout=settings.SCAN_TIMEOUT,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))