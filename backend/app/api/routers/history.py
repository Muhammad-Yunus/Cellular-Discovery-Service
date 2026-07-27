from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services import HistoryService
from app.schemas.scan import (
    ScanSessionListResponse,
    ScanSessionResponse,
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
    db: Session = Depends(get_db),
):
    service = HistoryService(db=db)
    return service.get_sessions(
        page=page,
        page_size=page_size,
        search=search,
        sort=sort,
    )


@router.get("/{scan_id}", response_model=ScanSessionResponse)
def get_scan(
    scan_id: int,
    db: Session = Depends(get_db),
):
    service = HistoryService(db=db)
    result = service.get_session(scan_id)

    if not result:
        raise HTTPException(status_code=404, detail="Scan not found")

    return result


@router.delete("/{scan_id}", response_model=ScanDeleteResponse)
def delete_scan(
    scan_id: int,
    db: Session = Depends(get_db),
):
    service = HistoryService(db=db)
    deleted = service.delete_session(scan_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Scan not found")

    return ScanDeleteResponse(
        message="Scan deleted successfully",
        id=scan_id,
    )
