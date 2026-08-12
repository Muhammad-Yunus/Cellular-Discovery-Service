"""Mock GPS provider for testing and local development.

Always returns a fixed Jakarta coordinate unless MOCK_GPS_FAIL=1 is set in the
environment, in which case it raises GPSReadError to simulate a hardware /
signal failure. This dual-mode behavior is crucial for end-to-end tests (S06)
to verify the mission executor's failure handling and the 503 response path.
"""

import os

from app.gps.exceptions import GPSReadError
from app.gps.schemas import GPSLocation


class MockGPSProvider:
    def __init__(
        self,
        latitude: float = -6.150676643667096,
        longitude: float = 106.89665223346297,
        altitude: float = 50.0,
    ):
        self._latitude = latitude
        self._longitude = longitude
        self._altitude = altitude

    def get_location(self) -> GPSLocation:
        # Test-only fault injection: when MOCK_GPS_FAIL=1, raise as if the device
        # returned unreadable data.
        if os.environ.get("MOCK_GPS_FAIL") == "1":
            raise GPSReadError("Simulated GPS read failure (MOCK_GPS_FAIL=1)")
        return GPSLocation(
            latitude=self._latitude,
            longitude=self._longitude,
            altitude=self._altitude,
            course_deg=None,
        )

    def is_available(self) -> bool:
        # Even when failing reads, the device is "available" — the operator
        # should retry, not skip the mission entirely.
        return True
