import json
import subprocess
import logging
from typing import Optional
from app.gps.schemas import GPSLocation
from app.gps.exceptions import GPSReadError

logger = logging.getLogger(__name__)


class CLIGPSProvider:
    """GPS Provider that uses the external GPS CLI tool."""

    def __init__(
        self,
        command: str = "/home/pi/GPS/build/gps",
        device: str = "/dev/ttyAMA0",
        baud: int = 9600,
        timeout: int = 10,
    ):
        self.command = command
        self.device = device
        self.baud = baud
        self.timeout = timeout

    def get_location(self) -> GPSLocation:
        """Get GPS location by calling the CLI tool."""
        cmd = [self.command, "-d", self.device, "-b", str(self.baud), "-j"]
        logger.info(f"Calling GPS CLI: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode != 0:
                logger.error(f"GPS CLI error: {result.stderr}")
                raise GPSReadError(f"GPS CLI failed: {result.stderr}")

            data = json.loads(result.stdout)
            logger.debug(f"GPS CLI output: {data}")

            if not data.get("has_fix", False):
                raise GPSReadError(
                    f"No GPS fix. Fix quality: {data.get('fix_quality', 0)}"
                )

            lat = data.get("latitude")
            lon = data.get("longitude")

            if lat is None or lon is None:
                raise GPSReadError("GPS data missing latitude or longitude")

            return GPSLocation(latitude=lat, longitude=lon)

        except subprocess.TimeoutExpired:
            logger.error(f"GPS CLI timed out after {self.timeout}s")
            raise GPSReadError(f"GPS CLI timeout after {self.timeout}s")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPS CLI output: {e}")
            raise GPSReadError(f"Invalid GPS JSON output: {e}")
        except FileNotFoundError:
            logger.error(f"GPS CLI not found: {self.command}")
            raise GPSReadError(f"GPS CLI not found: {self.command}")

    def is_available(self) -> bool:
        """Check if GPS is available by testing the CLI."""
        try:
            self.get_location()
            return True
        except Exception as e:
            logger.debug(f"GPS not available: {e}")
            return False
