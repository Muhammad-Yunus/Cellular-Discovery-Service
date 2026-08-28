from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.database import get_db
from app.services import MissionService
from app.schemas.mission import (
    MissionCreate,
    MissionDeleteResponse,
    MissionDetailResponse,
    MissionListResponse,
    MissionResponse,
    MissionUpdate,
)

router = APIRouter(prefix="/api/v1/missions", tags=["missions"])

MISSIONS_LIST_EXAMPLE = {
    "items": [
        {
            "id": 2236,
            "name": "TEST-RADIUS20-SPEED10-V2",
            "description": "Auto-generated mission dengan 1 tower",
            "status": "COMPLETED",
            "radius_meters": 50,
            "start_location_id": 6331,
            "current_location_id": 6331,
            "total_locations": 1,
            "visited_locations": 1,
            "progress_percent": 100.0,
            "started_at": "2026-08-28T06:00:36.834981+07:00",
            "completed_at": "2026-08-28T06:01:49.551265+07:00",
            "stopped_at": None,
            "created_at": "2026-08-28T06:00:26.430945+07:00",
            "updated_at": "2026-08-28T06:00:26.430945+07:00"
        }
    ],
    "total": 93,
    "page": 1,
    "page_size": 1
}


@router.post("", response_model=MissionResponse, status_code=201)
def create_mission(
    payload: MissionCreate,
    db: Session = Depends(get_db),
):
    service = MissionService(db)
    return service.create(payload)


@router.get(
    "",
    response_model=MissionListResponse,
    responses={
        200: {
            "description": "Daftar misi",
            "content": {
                "application/json": {
                    "example": MISSIONS_LIST_EXAMPLE
                }
            }
        }
    }
)
def list_missions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str | None = None,
    search: str | None = None,
    sort: str = Query("-created_at", description="Sort field with optional '-' prefix for DESC"),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    db: Session = Depends(get_db),
):
    if start_time and end_time:
        if start_time.timestamp() > end_time.timestamp():
            raise HTTPException(
                status_code=422,
                detail="start_time cannot be greater than end_time",
            )

    service = MissionService(db)
    return service.list(page, page_size, status, search, sort, start_time, end_time)


@router.get("/{mission_id}", response_model=MissionDetailResponse)
def get_mission(
    mission_id: int,
    db: Session = Depends(get_db),
):
    service = MissionService(db)
    result = service.get_detail(mission_id)
    if not result:
        raise HTTPException(status_code=404, detail="Mission not found")
    return result


@router.patch("/{mission_id}", response_model=MissionResponse)
def update_mission(
    mission_id: int,
    payload: MissionUpdate,
    db: Session = Depends(get_db),
):
    service = MissionService(db)
    return service.update(mission_id, payload)


@router.delete("/{mission_id}", response_model=MissionDeleteResponse)
def delete_mission(
    mission_id: int,
    db: Session = Depends(get_db),
):
    service = MissionService(db)
    service.delete(mission_id)
    return MissionDeleteResponse(
        message="Mission deleted successfully",
        id=mission_id,
    )
