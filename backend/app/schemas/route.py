from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RouteItem(BaseModel):
    location_id: int
    sequence_order: Optional[int] = None
    cellular_tower_id: str
    cellular_tower_name: Optional[str] = None
    latitude: float
    longitude: float
    status: str
    distance_from_previous_meters: Optional[float] = None
    bearing_from_previous_degrees: Optional[float] = None
    estimated_arrival_time: Optional[datetime] = None
    actual_visit_time: Optional[datetime] = None
    scan_session_id: Optional[int] = None
    visited_at: Optional[datetime] = None


class RouteResponse(BaseModel):
    mission_id: int
    mission_name: str
    status: str
    start_location_id: Optional[int] = None
    total_distance_meters: float
    items: list[RouteItem]


class ReorderItem(BaseModel):
    location_id: int
    sequence_order: int


ReorderRequest = list[ReorderItem]


class SkipRequest(BaseModel):
    location_id: int


class SkipResponse(BaseModel):
    message: str
    location_id: int
