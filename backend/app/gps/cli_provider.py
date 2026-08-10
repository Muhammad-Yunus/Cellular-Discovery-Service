import json
import subprocess
import logging
import threading
import time
from pathlib import Path
from typing import Optional
from app.gps.schemas import GPSLocation
from app.gps.exceptions import GPSReadError

logger = logging.getLogger(__name__)

# Module-level lock so only one gps CLI invocation runs at a time.
# The /dev/ttyAMA0 UART is a shared resource — two simultaneous reads
# from the scan API and the /ws/gps websocket will starve each other
# and both time out. Serialise them.
_gps_cli_lock = threading.Lock()
_gps_cli_last_error_at: float = 0.0
_gps_cli_last_error_msg: str = ""


def _recent_gps_error(cooldown: float = 5.0) -> Optional[str]:
    """If a GPS read failed recently, short-circuit subsequent callers
    for `cooldown` seconds to avoid piling up timeouts.
    """
    global _gps_cli_last_error_at, _gps_cli_last_error_msg
    if _gps_cli_last_error_msg and (time.time() - _gps_cli_last_error_at) < cooldown:
        return _gps_cli_last_error_msg
    return None


def _record_gps_error(msg: str) -> None:
    global _gps_cli_last_error_at, _gps_cli_last_error_msg
    _gps_cli_last_error_at = time.time()
    _gps_cli_last_error_msg = msg


def _clear_gps_error() -> None:
    global _gps_cli_last_error_at, _gps_cli_last_error_msg
    _gps_cli_last_error_at = 0.0
    _gps_cli_last_error_msg = ""


class CLIGPSProvider:
    """GPS Provider that uses the external GPS CLI tool."""

    def __init__(
        self,
        command: str = "/home/pi/GPS/build/gps",
        device: str = "/dev/ttyAMA0",
        baud: int = 9600,
        timeout: int = 30,
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

        Thread-safe via module-level lock. Short-circuits for a few seconds
        after a recent failure so concurrent callers don't pile up timeouts.
        """
        recent = _recent_gps_error()
        if recent:
            raise GPSReadError(recent)

        with _gps_cli_lock:
            return self._get_location_locked()

    def _get_location_locked(self) -> GPSLocation:
        cmd_base = [
            self.command, "-d", self.device, "-b", str(self.baud),
            "-w", "-j", "-c", str(self.count),
        ]
        # The CLI emits a stream of GPS readings. Early entries have
        # has_fix=true but fix_quality=0 / satellites_used=0 because the
        # receiver hasn't fully acquired sats yet. We want the LAST line
        # with real sat info, since by then the receiver has stabilised.
        cmd = (
            " ".join(cmd_base)
            + " | jq -c 'select(.has_fix==true and (.satellites_used // 0) > 0)'"
            + " | tail -1"
        )
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
                msg = f"GPS CLI failed (rc={result.returncode}): {result.stderr.strip()}"
                logger.error(msg)
                _record_gps_error(msg)
                raise GPSReadError(msg)

            output = result.stdout.strip()
            if not output:
                msg = "No GPS fix found. GPS may need more time to acquire fix."
                logger.warning(msg)
                _record_gps_error(msg)
                raise GPSReadError(msg)

            data = json.loads(output)
            logger.debug(f"GPS CLI output: {data}")

            lat = data.get("latitude")
            lon = data.get("longitude")
            alt = data.get("altitude_m")  # GPS CLI field name

            if lat is None or lon is None:
                msg = "GPS data missing latitude or longitude"
                _record_gps_error(msg)
                raise GPSReadError(msg)

            _clear_gps_error()
            return GPSLocation(
                latitude=lat,
                longitude=lon,
                altitude=alt if alt and alt > 0 else None,
            )

        except subprocess.TimeoutExpired:
            msg = f"GPS CLI timeout after {self.timeout}s"
            logger.error(msg)
            _record_gps_error(msg)
            raise GPSReadError(msg)
        except json.JSONDecodeError as e:
            msg = f"Invalid GPS JSON output: {e}"
            logger.error(msg)
            _record_gps_error(msg)
            raise GPSReadError(msg)
        except FileNotFoundError:
            msg = f"GPS CLI not found: {self.command}"
            logger.error(msg)
            _record_gps_error(msg)
            raise GPSReadError(msg)

    def is_available(self) -> bool:
        """Check if GPS is available by testing the CLI."""
        try:
            self.get_location()
            return True
        except Exception as e:
            logger.debug(f"GPS not available: {e}")
            return False