from pydantic import BaseModel
from typing import Optional


class GPSLocation(BaseModel):
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
    course_deg: Optional[float] = None
    """Heading in degrees (0-360) from true north. None if unavailable."""
