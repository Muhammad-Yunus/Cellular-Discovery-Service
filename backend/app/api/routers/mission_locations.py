from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services import LocationService
from app.schemas.mission_location import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    DeleteLocationResponse,
    LocationListResponse,
    MissionLocationResponse,
    UploadLocationResponse,
)

router = APIRouter(prefix="/api/v1/missions", tags=["missions"])


@router.post("/{mission_id}/locations/upload", response_model=UploadLocationResponse)
def upload_locations(
    mission_id: int,
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    if file is None:
        raise HTTPException(status_code=422, detail="No file uploaded")

    file_content = file.file.read()
    service = LocationService(db)
    return service.upload(mission_id, file_content)


@router.get("/{mission_id}/locations", response_model=LocationListResponse)
def list_locations(
    mission_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    db: Session = Depends(get_db),
):
    service = LocationService(db)
    return service.list_locations(mission_id, page, page_size, search)


@router.get("/{mission_id}/locations/{location_id}", response_model=MissionLocationResponse)
def get_location(
    mission_id: int,
    location_id: int,
    db: Session = Depends(get_db),
):
    service = LocationService(db)
    return service.get_location(mission_id, location_id)


@router.delete("/{mission_id}/locations/{location_id}", response_model=DeleteLocationResponse)
def delete_location(
    mission_id: int,
    location_id: int,
    db: Session = Depends(get_db),
):
    service = LocationService(db)
    return service.delete_location(mission_id, location_id)


@router.post("/{mission_id}/locations/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_locations(
    mission_id: int,
    body: BulkDeleteRequest,
    db: Session = Depends(get_db),
):
    service = LocationService(db)
    return service.bulk_delete(mission_id, body.upload_batch_id)
