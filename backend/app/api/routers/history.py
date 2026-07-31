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
    # Validasi rentang waktu: jika keduanya diatur dan start > end, kembalikan error
    if start_time and end_time:
        if start_time.timestamp() > end_time.timestamp():
            raise HTTPException(
                status_code=422,
                detail="start_time cannot be greater than end_time",
            )

    # Validasi filter RAT: harus mengandung setidaknya 1 huruf, kecuali ALL
    if rat is not None:
        rat_stripped = rat.strip()
        # EMPTY string or whitespace-only → invalid (except ALL)
        if rat_stripped == "" or rat_stripped == " ":
            raise HTTPException(
                status_code=422,
                detail="Filter RAT harus berisi minimal satu karakter alfabet atau ALL",
            )
        # Check if it's ALL (special keyword, skip filter)
        # Otherwise verify it contains at least one alphabetic character
        if not any(c.isalpha() for c in rat_stripped):
            raise HTTPException(
                status_code=422,
                detail="Filter RAT harus mengandung huruf alfabet (contoh: GSM, LTE)",
            )

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
