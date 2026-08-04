"""Integration tests for SerialGPSProvider with mocked serial.Serial."""
import pytest
from unittest.mock import patch, MagicMock

from app.gps.serial_provider import SerialGPSProvider
from app.gps.exceptions import GPSNotFoundError, GPSReadError


class TestSerialGPSProviderIntegration:
    """Integration tests using mocked serial.Serial."""

    def test_get_location_with_serial_mock(self):
        """Test get_location with mocked serial.Serial (full stack)."""
        mock_conn = MagicMock()
        mock_conn.is_open = True
        mock_conn.readline.return_value = b"$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,47.0,M,,*47"

        with patch("app.gps.serial_provider.serial.Serial", return_value=mock_conn):
            provider = SerialGPSProvider(port="/dev/ttyTEST", baudrate=9600)
            location = provider.get_location()

            assert location.latitude == pytest.approx(48.1173, rel=1e-2)
            assert location.longitude == pytest.approx(11.5167, rel=1e-2)

    def test_get_location_read_error(self):
        """Test get_location raises GPSReadError on serial read failure."""
        mock_conn = MagicMock()
        mock_conn.is_open = True
        mock_conn.readline.side_effect = OSError("device disconnected")

        with patch("app.gps.serial_provider.serial.Serial", return_value=mock_conn):
            provider = SerialGPSProvider(port="/dev/ttyTEST")
            with pytest.raises(GPSReadError) as exc_info:
                provider.get_location()
            assert "Failed to read from serial port" in str(exc_info.value)

    def test_get_location_empty_line(self):
        """Test get_location raises GPSReadError on empty read."""
        mock_conn = MagicMock()
        mock_conn.is_open = True
        mock_conn.readline.return_value = b""

        with patch("app.gps.serial_provider.serial.Serial", return_value=mock_conn):
            provider = SerialGPSProvider(port="/dev/ttyTEST")
            with pytest.raises(GPSReadError) as exc_info:
                provider.get_location()
            assert "Empty GPS data" in str(exc_info.value)

    def test_get_location_parse_error_index(self):
        """Test get_location raises GPSReadError on IndexError during parse."""
        mock_conn = MagicMock()
        mock_conn.is_open = True
        # Valid GGA with enough parts but invalid content that causes IndexError
        mock_conn.readline.return_value = b"$GPGGA,123519,,,N,,E,1,08,0.9,545.4,M,47.0,M,,*47"

        with patch("app.gps.serial_provider.serial.Serial", return_value=mock_conn):
            provider = SerialGPSProvider(port="/dev/ttyTEST")
            with pytest.raises(GPSReadError) as exc_info:
                provider.get_location()
            assert "Empty coordinate" in str(exc_info.value)

    def test_get_location_parse_error_value(self):
        """Test get_location raises GPSReadError on non-numeric coordinate."""
        mock_conn = MagicMock()
        mock_conn.is_open = True
        mock_conn.readline.return_value = b"$GPGGA,123519,notanum,N,01131.000,E,1,08,0.9,545.4,M,47.0,M,,*47"

        with patch("app.gps.serial_provider.serial.Serial", return_value=mock_conn):
            provider = SerialGPSProvider(port="/dev/ttyTEST")
            with pytest.raises(GPSReadError) as exc_info:
                provider.get_location()
            assert "Failed to parse GPS coordinates" in str(exc_info.value)

    def test_serial_exception_raises_gps_not_found(self):
        """Test serial.SerialException is converted to GPSNotFoundError."""
        import serial
        with patch(
            "app.gps.serial_provider.serial.Serial",
            side_effect=serial.SerialException("no such device"),
        ):
            provider = SerialGPSProvider(port="/dev/ttyNOPE")
            with pytest.raises(GPSNotFoundError) as exc_info:
                provider.get_location()
            assert exc_info.value.device == "/dev/ttyNOPE"

    def test_is_available_returns_true_when_open(self):
        """Test is_available returns True when connection is open."""
        mock_conn = MagicMock()
        mock_conn.is_open = True

        with patch("app.gps.serial_provider.serial.Serial", return_value=mock_conn):
            provider = SerialGPSProvider(port="/dev/ttyTEST")
            assert provider.is_available() is True

    def test_is_available_returns_false_on_exception(self):
        """Test is_available returns False when connection fails."""
        import serial
        with patch(
            "app.gps.serial_provider.serial.Serial",
            side_effect=serial.SerialException("nope"),
        ):
            provider = SerialGPSProvider(port="/dev/ttyNOPE")
            assert provider.is_available() is False

    def test_connection_reused_when_open(self):
        """Test _connect returns existing connection when still open."""
        mock_conn = MagicMock()
        mock_conn.is_open = True

        with patch("app.gps.serial_provider.serial.Serial", return_value=mock_conn) as mock_serial:
            provider = SerialGPSProvider(port="/dev/ttyTEST")
            conn1 = provider._connect()
            conn2 = provider._connect()
            assert conn1 is conn2
            # Serial constructor called only once
            assert mock_serial.call_count == 1

    def test_connection_recreated_when_closed(self):
        """Test _connect creates new connection when closed."""
        mock_conn1 = MagicMock()
        mock_conn1.is_open = False
        mock_conn2 = MagicMock()
        mock_conn2.is_open = True

        with patch("app.gps.serial_provider.serial.Serial") as mock_serial:
            mock_serial.side_effect = [mock_conn1, mock_conn2]
            provider = SerialGPSProvider(port="/dev/ttyTEST")
            _ = provider._connect()
            # Force the cached connection to be considered closed
            provider._connection = mock_conn1
            _ = provider._connect()
            assert mock_serial.call_count == 2
