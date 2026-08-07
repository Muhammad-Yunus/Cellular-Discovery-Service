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
        count: int = 5,
    ):
        self.command = command
        self.device = device
        self.baud = baud
        self.timeout = timeout
        self.count = count

    def get_location(self) -> GPSLocation:
        """Get GPS location by calling the CLI tool.
        
        Uses jq pipeline to find first line with has_fix=true AND fix_quality>0.
        GPS needs multiple reads to acquire fix, so we read up to `count` times.
        """
        cmd_base = [
            self.command, "-d", self.device, "-b", str(self.baud),
            "-w", "-j", "-c", str(self.count),
        ]
        # Pipe through jq to get compact single-line JSON with fix
        cmd = " ".join(cmd_base) + " | jq -c 'select(.has_fix==true and .fix_quality>0)' | head -1"
        logger.info(f"Calling GPS CLI: {cmd}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                shell=True,
            )

            if result.returncode != 0:
                logger.error(f"GPS CLI error: {result.stderr}")
                raise GPSReadError(f"GPS CLI failed: {result.stderr}")

            output = result.stdout.strip()
            if not output:
                raise GPSReadError(
                    "No GPS fix found. GPS may need more time to acquire fix."
                )
            
            data = json.loads(output)
            logger.debug(f"GPS CLI output: {data}")

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
