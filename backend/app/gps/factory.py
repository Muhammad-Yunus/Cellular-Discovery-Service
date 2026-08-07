import os
from app.gps.provider import GPSProvider
from app.gps.mock_provider import MockGPSProvider
from app.gps.serial_provider import SerialGPSProvider
from app.gps.cli_provider import CLIGPSProvider


def create_gps_provider(provider_type: str, **kwargs) -> GPSProvider:
    if provider_type == "mock":
        return MockGPSProvider(**kwargs)
    elif provider_type == "serial":
        return SerialGPSProvider(**kwargs)
    elif provider_type == "cli":
        # Allow env overrides for production tuning
        command = kwargs.pop("command", "/home/pi/GPS/build/gps")
        device = kwargs.pop("device", os.environ.get("GPS_CLI_DEVICE", "/dev/ttyAMA0"))
        baud = int(kwargs.pop("baud", os.environ.get("GPS_CLI_BAUD", "9600")))
        timeout = int(kwargs.pop("timeout", os.environ.get("GPS_CLI_TIMEOUT", "60")))
        count = int(kwargs.pop("count", os.environ.get("GPS_CLI_COUNT", "10")))
        return CLIGPSProvider(
            command=command,
            device=device,
            baud=baud,
            timeout=timeout,
            count=count,
        )
    else:
        raise ValueError(f"Unknown GPS provider type: {provider_type}")

