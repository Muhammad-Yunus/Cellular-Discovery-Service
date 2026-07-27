from typing import Protocol
from app.gps.schemas import GPSLocation


class GPSProvider(Protocol):
    def get_location(self) -> GPSLocation:
        """Get current GPS location."""
        ...

    def is_available(self) -> bool:
        """Check if GPS provider is available."""
        ...
