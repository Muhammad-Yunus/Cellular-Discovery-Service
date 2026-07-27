import pytest
from unittest.mock import patch, MagicMock
from app.gps.serial_provider import SerialGPSProvider
from app.gps.exceptions import GPSNotFoundError, GPSReadError


class TestSerialGPSProvider:
    def setup_method(self):
        self.provider = SerialGPSProvider(port="/dev/ttyUSB0")

    @patch("app.gps.serial_provider.serial.Serial")
    def test_connect_success(self, mock_serial_class):
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial_class.return_value = mock_serial

        result = self.provider._connect()

        assert result == mock_serial

    @patch("app.gps.serial_provider.serial.Serial")
    def test_connect_cached(self, mock_serial_class):
        mock_serial = MagicMock()
        mock_serial.is_open = True
        mock_serial_class.return_value = mock_serial

        self.provider._connection = mock_serial
        result = self.provider._connect()

        assert result == mock_serial
        mock_serial_class.assert_not_called()

    @patch("app.gps.serial_provider.serial.Serial")
    def test_connect_not_found(self, mock_serial_class):
        from serial import SerialException
        mock_serial_class.side_effect = SerialException("Port not found")

        with pytest.raises(GPSNotFoundError):
            self.provider._connect()

    def test_get_location(self):
        sentence = "$GPGGA,123519,0609.040,S,10653.798,E,1,08,0.9,545.4,M,47.0,M,,*47"
        location = self.provider._parse_nmea(sentence)

        assert location.latitude < 0
        assert location.longitude > 0

    def test_parse_nmea_not_gga(self):
        sentence = "$GPRMC,123519,A,4807.038,N,01131.000,E"

        with pytest.raises(GPSReadError):
            self.provider._parse_nmea(sentence)

    def test_parse_nmea_invalid_format(self):
        sentence = "$GPGGA,123519"

        with pytest.raises(GPSReadError):
            self.provider._parse_nmea(sentence)

    def test_parse_coordinate_empty(self):
        with pytest.raises(GPSReadError):
            self.provider._parse_coordinate("", "N")

    def test_parse_coordinate_north(self):
        result = self.provider._parse_coordinate("4807.038", "N")

        assert result == pytest.approx(48.1173, rel=1e-2)

    def test_parse_coordinate_south(self):
        result = self.provider._parse_coordinate("0609.040", "S")

        assert result == pytest.approx(-6.1507, rel=1e-2)

    def test_parse_coordinate_east(self):
        result = self.provider._parse_coordinate("01131.000", "E")

        assert result == pytest.approx(11.5167, rel=1e-2)

    def test_parse_coordinate_west(self):
        result = self.provider._parse_coordinate("01131.000", "W")

        assert result == pytest.approx(-11.5167, rel=1e-2)

    def test_is_available_false(self):
        self.provider._connection = None

        with patch("app.gps.serial_provider.serial.Serial", side_effect=Exception):
            assert self.provider.is_available() is False

    def test_close(self):
        mock_conn = MagicMock()
        mock_conn.is_open = True
        self.provider._connection = mock_conn

        self.provider.close()

        mock_conn.close.assert_called_once()
        assert self.provider._connection is None

    def test_close_already_closed(self):
        self.provider._connection = None
        self.provider.close()
