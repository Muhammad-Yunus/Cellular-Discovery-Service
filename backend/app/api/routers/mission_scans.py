from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.database import get_db
from app.services import MissionScanService
from app.schemas.scan import PaginatedResponse

router = APIRouter(prefix="/api/v1/missions", tags=["missions"])


MISSION_SCANS_EXAMPLE = {
    "items": [
        {
            "id": 2110,
            "scan_session_id": 2199,
            "scan_time": "2026-08-28T06:02:46.303534+07:00",
            "band": "5",
            "latitude": -6.150570602683586,
            "longitude": 106.8972906967608,
            "mission_location_id": 6331,
            "cellular_tower_id": "TWR-001",
            "cellular_tower_name": "Tower-1",
            "created_at": "2026-08-28T06:02:46.303534+07:00",
            "operator_name": "Hutchison 3",
            "mcc": "510",
            "mnc": "89",
            "rat": "LTE",
            "status": "Available",
            "frequency_mhz": 958.6,
            "earfcn": 3786,
            "pci": 0,
            "rsrp": -34.8,
            "rsrq": None,
            "snr": None
        }
    ],
    "total": 156,
    "page": 1,
    "page_size": 1,
    "total_pages": 156
}


@router.get(
    "/{mission_id}/scans",
    response_model=PaginatedResponse,
    responses={
        200: {
            "description": "Daftar scan results untuk mission",
            "content": {
                "application/json": {
                    "example": MISSION_SCANS_EXAMPLE
                }
            }
        }
    }
)
def list_mission_scans(
    mission_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    sort: str = "-scan_time",
    rat: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    db: Session = Depends(get_db),
):
    service = MissionScanService(db=db)
    try:
        return service.get_mission_scans(
            mission_id=mission_id,
            page=page,
            page_size=page_size,
            search=search,
            sort=sort,
            rat=rat,
            start_time=start_time,
            end_time=end_time,
        )
    except ValueError as e:
        msg = str(e)
        if msg == "Mission not found":
            raise HTTPException(status_code=404, detail="Mission not found")
        raise HTTPException(status_code=422, detail=msg)


@router.get("/{mission_id}/scans/export")
def export_mission_scans(
    mission_id: int,
    search: str | None = None,
    sort: str = "-scan_time",
    rat: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    db: Session = Depends(get_db),
):
    service = MissionScanService(db=db)
    try:
        csv_data = service.get_mission_csv(
            mission_id=mission_id,
            search=search,
            sort=sort,
            rat=rat,
            start_time=start_time,
            end_time=end_time,
        )
    except ValueError as e:
        msg = str(e)
        if msg == "Mission not found":
            raise HTTPException(status_code=404, detail="Mission not found")
        raise HTTPException(status_code=422, detail=msg)

    response = Response(content=csv_data, media_type="text/csv")
    response.headers[
        "Content-Disposition"
    ] = f'attachment; filename="mission_{mission_id}_scans.csv"'
    return response
