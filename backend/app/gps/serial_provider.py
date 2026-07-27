import serial
import logging
from app.gps.schemas import GPSLocation
from app.gps.exceptions import GPSNotFoundError, GPSReadError

logger = logging.getLogger(__name__)


class SerialGPSProvider:
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600, timeout: int = 5):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._connection = None

    def _connect(self) -> serial.Serial:
        if self._connection and self._connection.is_open:
            return self._connection

        try:
            self._connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
            )
            return self._connection
        except serial.SerialException as e:
            raise GPSNotFoundError(self.port)

    def get_location(self) -> GPSLocation:
        conn = self._connect()

        try:
            line = conn.readline().decode("ascii", errors="replace").strip()
        except Exception as e:
            raise GPSReadError(f"Failed to read from serial port: {e}")

        if not line:
            raise GPSReadError("Empty GPS data")

        return self._parse_nmea(line)

    def _parse_nmea(self, sentence: str) -> GPSLocation:
        if not sentence.startswith("$GPGGA") and not sentence.startswith("$GNGGA"):
            raise GPSReadError(f"Not a GGA sentence: {sentence}")

        parts = sentence.split(",")
        if len(parts) < 6:
            raise GPSReadError(f"Invalid GGA sentence: {sentence}")

        try:
            lat_raw = parts[2]
            lat_dir = parts[3]
            lon_raw = parts[4]
            lon_dir = parts[5]

            lat = self._parse_coordinate(lat_raw, lat_dir)
            lon = self._parse_coordinate(lon_raw, lon_dir)

            return GPSLocation(latitude=lat, longitude=lon)
        except (IndexError, ValueError) as e:
            raise GPSReadError(f"Failed to parse GPS coordinates: {e}")

    def _parse_coordinate(self, raw: str, direction: str) -> float:
        if not raw or not direction:
            raise GPSReadError("Empty coordinate")

        if direction in ("N", "S"):
            degrees = int(raw[:2])
            minutes = float(raw[2:])
        else:
            degrees = int(raw[:3])
            minutes = float(raw[3:])

        decimal = degrees + minutes / 60.0

        if direction in ("S", "W"):
            decimal = -decimal

        return decimal

    def is_available(self) -> bool:
        try:
            conn = self._connect()
            return conn.is_open
        except Exception:
            return False

    def close(self):
        if self._connection and self._connection.is_open:
            self._connection.close()
            self._connection = None
