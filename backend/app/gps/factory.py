from app.gps.provider import GPSProvider
from app.gps.mock_provider import MockGPSProvider
from app.gps.serial_provider import SerialGPSProvider


def create_gps_provider(provider_type: str, **kwargs) -> GPSProvider:
    if provider_type == "mock":
        return MockGPSProvider(**kwargs)
    elif provider_type == "serial":
        return SerialGPSProvider(**kwargs)
    else:
        raise ValueError(f"Unknown GPS provider type: {provider_type}")
