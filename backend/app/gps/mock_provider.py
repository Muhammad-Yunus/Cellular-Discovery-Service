from app.gps.schemas import GPSLocation


class MockGPSProvider:
    def __init__(
        self,
        latitude: float = -6.150676643667096,
        longitude: float = 106.89665223346297,
    ):
        self._latitude = latitude
        self._longitude = longitude

    def get_location(self) -> GPSLocation:
        return GPSLocation(
            latitude=self._latitude,
            longitude=self._longitude,
        )

    def is_available(self) -> bool:
        return True
