from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.database import get_db
from app.services import MissionScanService
from app.schemas.scan import PaginatedResponse

router = APIRouter(prefix="/api/v1/missions", tags=["missions"])


@router.get("/{mission_id}/scans", response_model=PaginatedResponse)
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
