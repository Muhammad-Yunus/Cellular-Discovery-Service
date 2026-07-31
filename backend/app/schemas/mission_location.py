from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MissionLocationResponse(BaseModel):
    id: int
    mission_id: int
    cellular_tower_id: str
    cellular_tower_name: Optional[str] = None
    latitude: float
    longitude: float
    upload_batch_id: Optional[str] = None
    sequence_order: Optional[int] = None
    status: str
    distance_from_previous_meters: Optional[float] = None
    bearing_from_previous_degrees: Optional[float] = None
    estimated_arrival_time: Optional[datetime] = None
    actual_visit_time: Optional[datetime] = None
    scan_session_id: Optional[int] = None
    visited_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LocationListResponse(BaseModel):
    items: list[MissionLocationResponse]
    total: int
    page: int
    page_size: int


class UploadRowError(BaseModel):
    row: int
    error: str


class UploadLocationResponse(BaseModel):
    upload_batch_id: str
    mission_id: int
    total_rows: int
    inserted: int
    updated: int
    skipped: int
    errors: list[UploadRowError]


class DeleteLocationResponse(BaseModel):
    message: str
    id: int


class BulkDeleteRequest(BaseModel):
    upload_batch_id: str


class BulkDeleteResponse(BaseModel):
    message: str
    deleted: int
