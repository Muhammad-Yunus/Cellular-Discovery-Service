from app.gps.provider import GPSProvider
from app.gps.mock_provider import MockGPSProvider
from app.gps.serial_provider import SerialGPSProvider
from app.gps.cli_provider import CLIGPSProvider
from app.gps.moving_mock_provider import MovingMockGPSProvider
from app.config.settings import get_settings


def _parse_waypoints(s: str) -> list[tuple[float, float]]:
    """Parse "lat,lon:lat,lon:..." into list of (lat, lon) tuples."""
    if not s:
        return []
    out = []
    for pair in s.split(":"):
        pair = pair.strip()
        if not pair:
            continue
        lat, lon = pair.split(",")
        out.append((float(lat), float(lon)))
    return out


def create_gps_provider(provider_type: str, **kwargs) -> GPSProvider:
    settings = get_settings()
    if provider_type == "mock":
        return MockGPSProvider(**kwargs)
    elif provider_type == "moving_mock":
        if "start_lat" not in kwargs:
            kwargs["start_lat"] = settings.MOCK_GPS_START_LAT
        if "start_lon" not in kwargs:
            kwargs["start_lon"] = settings.MOCK_GPS_START_LON
        if "waypoints" not in kwargs:
            kwargs["waypoints"] = _parse_waypoints(settings.MOCK_GPS_WAYPOINTS)
        if "loiter_radius_m" not in kwargs:
            kwargs["loiter_radius_m"] = settings.MOCK_GPS_LOITER_RADIUS_M
        if "cruise_speed_ms" not in kwargs:
            kwargs["cruise_speed_ms"] = settings.MOCK_GPS_SPEED_MS
        if "loiter_laps" not in kwargs:
            kwargs["loiter_laps"] = settings.MOCK_GPS_LOITER_LAPS
        return MovingMockGPSProvider(**kwargs)
    elif provider_type == "serial":
        return SerialGPSProvider(**kwargs)
    elif provider_type == "cli":
        # Allow env overrides for production tuning
        command = kwargs.pop("command", settings.CLI_COMMAND)
        device = kwargs.pop("device", settings.DEFAULT_GPS_TTY)
        baud = int(kwargs.pop("baud", settings.GPS_CLI_BAUD))
        timeout = int(kwargs.pop("timeout", settings.GPS_CLI_TIMEOUT))
        count = int(kwargs.pop("count", settings.GPS_CLI_COUNT))
        return CLIGPSProvider(
            command=command,
            device=device,
            baud=baud,
            timeout=timeout,
            count=count,
        )
    else:
        raise ValueError(f"Unknown GPS provider type: {provider_type}")

