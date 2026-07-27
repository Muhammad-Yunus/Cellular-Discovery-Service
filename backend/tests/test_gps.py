import pytest
from app.gps.mock_provider import MockGPSProvider
from app.gps.serial_provider import SerialGPSProvider
from app.gps.factory import create_gps_provider
from app.gps.exceptions import GPSNotFoundError, GPSReadError


class TestMockGPSProvider:
    def setup_method(self):
        self.provider = MockGPSProvider()

    def test_get_location(self):
        location = self.provider.get_location()

        assert location.latitude == -6.150676643667096
        assert location.longitude == 106.89665223346297

    def test_get_location_custom(self):
        provider = MockGPSProvider(latitude=1.0, longitude=2.0)
        location = provider.get_location()

        assert location.latitude == 1.0
        assert location.longitude == 2.0

    def test_is_available(self):
        assert self.provider.is_available() is True


class TestSerialGPSProvider:
    def setup_method(self):
        self.provider = SerialGPSProvider()

    def test_parse_nmea_valid(self):
        sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,47.0,M,,*47"
        location = self.provider._parse_nmea(sentence)

        assert location.latitude == pytest.approx(48.1173, rel=1e-2)
        assert location.longitude == pytest.approx(11.5167, rel=1e-2)

    def test_parse_nmea_south_west(self):
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


class TestGPSFactory:
    def test_create_mock_provider(self):
        provider = create_gps_provider("mock")

        assert isinstance(provider, MockGPSProvider)

    def test_create_serial_provider(self):
        provider = create_gps_provider("serial", port="/dev/ttyUSB0")

        assert isinstance(provider, SerialGPSProvider)

    def test_create_unknown_provider(self):
        with pytest.raises(ValueError):
            create_gps_provider("unknown")
