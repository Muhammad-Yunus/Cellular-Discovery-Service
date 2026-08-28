from fastapi import APIRouter, Depends, HTTPException, Query, Response
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


SCANS_LIST_EXAMPLE = {
    "items": [
        {
            "id": 2119,
            "scan_session_id": 2200,
            "scan_time": "2026-08-28T09:40:08.748887+07:00",
            "band": "5",
            "latitude": -6.150456,
            "longitude": 106.896944,
            "mission_location_id": None,
            "cellular_tower_id": None,
            "cellular_tower_name": None,
            "created_at": "2026-08-28T09:40:08.748887+07:00",
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
    ],
    "total": 1754,
    "page": 1,
    "page_size": 1,
    "total_pages": 1754
}


@router.get(
    "",
    response_model=PaginatedResponse,
    responses={
        200: {
            "description": "Daftar scan results",
            "content": {
                "application/json": {
                    "example": SCANS_LIST_EXAMPLE
                }
            }
        }
    }
)
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

    # Validasi filter RAT — hanya GSM, LTE, UMTS, atau ALL (case-insensitive)
    if rat is not None:
        rat_stripped = rat.strip()
        if rat_stripped and rat_stripped.upper() not in {"GSM", "LTE", "UMTS", "ALL"}:
            raise HTTPException(
                status_code=422,
                detail="Only GSM, LTE, UMTS, or ALL is allowed for the rat parameter",
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


@router.get("/export")
def export_scans(
    search: str | None = None,
    sort: str = "-scan_time",
    rat: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    db: Session = Depends(get_db),
):
    """Export all scan results matching filters to CSV."""
    # Validasi rentang waktu: jika keduanya diatur dan start > end, kembalikan error
    if start_time and end_time:
        if start_time.timestamp() > end_time.timestamp():
            raise HTTPException(
                status_code=422,
                detail="start_time cannot be greater than end_time",
            )

    # Validasi filter RAT — hanya GSM, LTE, UMTS, atau ALL (case-insensitive)
    if rat is not None:
        rat_stripped = rat.strip()
        if rat_stripped and rat_stripped.upper() not in {"GSM", "LTE", "UMTS", "ALL"}:
            raise HTTPException(
                status_code=422,
                detail="Only GSM, LTE, UMTS, or ALL is allowed for the rat parameter",
            )

    service = HistoryService(db=db)
    csv_data = service.get_all_csv(
        search=search,
        sort=sort,
        rat=rat,
        start_time=start_time,
        end_time=end_time,
    )
    response = Response(content=csv_data, media_type="text/csv")
    response.headers["Content-Disposition"] = 'attachment; filename="scan_export.csv"'
    return response


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
