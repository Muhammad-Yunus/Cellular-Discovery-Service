from pydantic import BaseModel
from typing import Optional


class GPSLocation(BaseModel):
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
