from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.schemas.mission_location import MissionLocationResponse


class MissionStatus(str, Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    READY = "READY"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class MissionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    radius_meters: Optional[int] = Field(default=None, gt=0)
    tty_port: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v):
        name = str(v).strip()
        if not name:
            raise ValueError("Mission name is required")
        return name


class MissionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    radius_meters: Optional[int] = Field(default=None, gt=0)
    tty_port: Optional[str] = None
    start_location_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v):
        if v is None:
            raise ValueError("Mission name is required")
        name = str(v).strip()
        if not name:
            raise ValueError("Mission name is required")
        return name


class MissionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: MissionStatus
    radius_meters: Optional[int] = None
    tty_port: Optional[str] = None
    start_location_id: Optional[int] = None
    current_location_id: Optional[int] = None
    total_locations: int
    visited_locations: int
    progress_percent: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MissionDetailResponse(MissionResponse):
    locations: list[MissionLocationResponse]


class MissionListResponse(BaseModel):
    items: list[MissionResponse]
    total: int
    page: int
    page_size: int


class MissionDeleteResponse(BaseModel):
    message: str
    id: int
