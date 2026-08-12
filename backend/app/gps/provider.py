from typing import Protocol
from app.gps.schemas import GPSLocation


class GPSProvider(Protocol):
    def get_location(self) -> GPSLocation:
        """Get current GPS location."""
        ...

    def is_available(self) -> bool:
        """Check if GPS provider is available."""
        ...

    def reset_start_time(self) -> None:
        """Reset the GPS provider's internal timer (e.g. for moving_mock restart).

        Default no-op; providers that support restart should override.
        """
        pass
