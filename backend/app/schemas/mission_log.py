from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class MissionLog(BaseModel):
    """
    Single log entry for a mission.
    """
    timestamp: str
    """ISO format timestamp (UTC)"""
    event_type: str
    """Event type: STARTED, GPS_FIX, SCANNING, ARRIVED, SKIPPED, FAILED, etc."""
    message: str
    """Descriptive message of the event"""


class MissionLogsResponse(BaseModel):
    """
    Paginated response for mission logs.
    """
    items: list[MissionLog]
    """List of log entries (sorted by timestamp DESC)"""
    total: int
    """Total number of log entries for this mission"""
    page: int
    """Current page number (1-indexed)"""
    page_size: int
    """Number of items per page"""
    total_pages: int
    """Total number of pages"""


class MissionLogsQueryParams(BaseModel):
    """
    Query parameters for paginated mission logs endpoint.
    """
    page: int = 1
    """Page number (default: 1)"""
    page_size: int = 10
    """Items per page (default: 10, max: 100)"""
