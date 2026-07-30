from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.database import get_db
from app.services import HistoryService
from app.schemas.scan import (
    ScanResultFlatResponse,
    PaginatedResponse,
    ScanDeleteResponse,
)

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])


@router.get("", response_model=PaginatedResponse)
def list_scans(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    sort: str = "-scan_time",
    rat: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    db: Session = Depends(get_db),
):
    service = HistoryService(db=db)
    return service.get_sessions(
        page=page,
        page_size=page_size,
        search=search,
        sort=sort,
        rat=rat,
        start_time=start_time,
        end_time=end_time,
    )


@router.get("/{result_id}", response_model=ScanResultFlatResponse)
def get_scan(
    result_id: int,
    db: Session = Depends(get_db),
):
    service = HistoryService(db=db)
    result = service.get_session(result_id)

    if not result:
        raise HTTPException(status_code=404, detail="Scan result not found")

    return result


@router.delete("/{result_id}", response_model=ScanDeleteResponse)
def delete_scan(
    result_id: int,
    db: Session = Depends(get_db),
):
    service = HistoryService(db=db)
    deleted = service.delete_session(result_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Scan result not found")

    return ScanDeleteResponse(
        message="Scan result deleted successfully",
        id=result_id,
    )
