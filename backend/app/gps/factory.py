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
        # Default CLI command and device
        command = kwargs.pop("command", "/home/pi/GPS/build/gps")
        device = kwargs.pop("device", "/dev/ttyAMA0")
        baud = kwargs.pop("baud", 9600)
        timeout = kwargs.pop("timeout", 10)
        return CLIGPSProvider(
            command=command,
            device=device,
            baud=baud,
            timeout=timeout,
        )
    else:
        raise ValueError(f"Unknown GPS provider type: {provider_type}")

