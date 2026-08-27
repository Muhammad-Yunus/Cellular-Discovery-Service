import re
from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
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


VALID_BANDS = {"8", "20", "28", "40", "42"}


def _validate_band(cls, v):
    if v is None:
        return v
    v = str(v).strip()
    # Accept numeric band identifiers (e.g. "8", "20", "40")
    if v in VALID_BANDS:
        return v
    raise ValueError(f"band must be a valid LTE band from {VALID_BANDS}")


class MissionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    radius_meters: Optional[int] = Field(default=None, ge=10, le=100)
    band: str  # Required: must be a valid LTE band (e.g., 8, 20, 40)

    @model_validator(mode="before")
    @classmethod
    def _convert_band(cls, data):
        if isinstance(data, dict) and "band" in data:
            data["band"] = str(data["band"])
        return data

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v):
        name = str(v).strip()
        if not name:
            raise ValueError("Mission name is required")
        return name

    @field_validator("band")
    @classmethod
    def _validate_band(cls, v):
        return _validate_band(cls, v)


class MissionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    radius_meters: Optional[int] = Field(default=None, ge=10, le=100)
    band: Optional[str] = None
    start_location_id: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def _convert_band(cls, data):
        if isinstance(data, dict) and "band" in data and data["band"] is not None:
            data["band"] = str(data["band"])
        return data

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v):
        if v is None:
            raise ValueError("Mission name is required")
        name = str(v).strip()
        if not name:
            raise ValueError("Mission name is required")
        return name

    @field_validator("band")
    @classmethod
    def _validate_band(cls, v):
        return _validate_band(cls, v)


class MissionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: MissionStatus
    radius_meters: Optional[int] = None
    band: Optional[str] = None
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
