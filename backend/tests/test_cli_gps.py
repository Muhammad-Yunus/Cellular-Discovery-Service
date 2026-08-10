import pytest
from unittest.mock import patch, MagicMock, call
from app.gps.cli_provider import CLIGPSProvider
from app.gps.mock_provider import MockGPSProvider
from app.gps.factory import create_gps_provider
from app.gps.exceptions import GPSReadError


class TestCLIGPSProvider:
    def setup_method(self):
        self.provider = CLIGPSProvider(
            command="/home/pi/GPS/build/gps",
            device="/dev/ttyAMA0",
            baud=9600,
            timeout=10,
        )

    def test_init_defaults(self):
        provider = CLIGPSProvider()
        assert provider.command == "/home/pi/GPS/build/gps"
        assert provider.device == "/dev/ttyAMA0"
        assert provider.baud == 9600
        assert provider.timeout == 10

    @patch("app.gps.cli_provider.subprocess.run")
    def test_get_location_with_fix(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"has_fix": true, "latitude": -6.15, "longitude": 106.90, "altitude_m": 50.0}',
            stderr="",
        )

        location = self.provider.get_location()

        assert location.latitude == -6.15
        assert location.longitude == 106.90
        assert location.altitude == 50.0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "/home/pi/GPS/build/gps" in args
        assert "-d" in args and "/dev/ttyAMA0" in args
        assert "-b" in args and "9600" in args
        assert "-j" in args

    @patch("app.gps.cli_provider.subprocess.run")
    def test_get_location_no_fix(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"has_fix": false, "fix_quality": 0, "satellites_used": 0}',
            stderr="",
        )

        with pytest.raises(GPSReadError, match="No GPS fix"):
            self.provider.get_location()

    @patch("app.gps.cli_provider.subprocess.run")
    def test_get_location_missing_lat_lon(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"has_fix": true}',
            stderr="",
        )

        with pytest.raises(GPSReadError, match="missing latitude or longitude"):
            self.provider.get_location()

    @patch("app.gps.cli_provider.subprocess.run")
    def test_get_location_cli_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Serial port open failed",
        )

        with pytest.raises(GPSReadError, match="GPS CLI failed"):
            self.provider.get_location()

    @patch("app.gps.cli_provider.subprocess.run")
    def test_get_location_timeout(self, mock_run):
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired(cmd="/home/pi/GPS/build/gps", timeout=10)

        with pytest.raises(GPSReadError, match="timeout after 10s"):
            self.provider.get_location()

    @patch("app.gps.cli_provider.subprocess.run")
    def test_get_location_invalid_json(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not json",
            stderr="",
        )

        with pytest.raises(GPSReadError, match="Invalid GPS JSON output"):
            self.provider.get_location()

    @patch("app.gps.cli_provider.subprocess.run")
    def test_get_location_file_not_found(self, mock_run):
        import os
        mock_run.side_effect = FileNotFoundError("/nonexistent/gps")

        with pytest.raises(GPSReadError, match="GPS CLI not found"):
            self.provider.get_location()

    @patch.object(CLIGPSProvider, "get_location")
    def test_is_available_true(self, mock_get):
        mock_get.return_value = MagicMock(latitude=-6.15, longitude=106.90, altitude=50.0)
        assert self.provider.is_available() is True

    @patch.object(CLIGPSProvider, "get_location")
    def test_is_available_false(self, mock_get):
        mock_get.side_effect = GPSReadError("GPS unavailable")
        assert self.provider.is_available() is False


class TestMockGPSProvider:
    def setup_method(self):
        self.provider = MockGPSProvider()

    def test_get_location_default(self):
        location = self.provider.get_location()
        assert location.latitude == pytest.approx(-6.1507, rel=1e-4)
        assert location.longitude == pytest.approx(106.8967, rel=1e-4)

    def test_is_available(self):
        assert self.provider.is_available() is True

    def test_get_location_custom(self):
        provider = MockGPSProvider(latitude=1.0, longitude=2.0)
        location = provider.get_location()
        assert location.latitude == 1.0
        assert location.longitude == 2.0

    @patch.dict("os.environ", {"MOCK_GPS_FAIL": "1"})
    def test_get_location_fail_injection(self):
        with pytest.raises(GPSReadError, match="Simulated GPS read failure"):
            self.provider.get_location()

    @patch.dict("os.environ", {"MOCK_GPS_FAIL": "1"})
    def test_is_available_still_true_when_failing(self):
        # Even when GPS "fails", the device is considered available
        # (operator should retry, not skip mission)
        assert self.provider.is_available() is True


class TestGPSFactory:
    def test_create_mock_provider(self):
        provider = create_gps_provider("mock")
        assert isinstance(provider, MockGPSProvider)

    def test_create_serial_provider(self):
        provider = create_gps_provider("serial", port="/dev/ttyUSB0")
        from app.gps.serial_provider import SerialGPSProvider
        assert isinstance(provider, SerialGPSProvider)

    def test_create_cli_provider(self):
        provider = create_gps_provider("cli")
        assert isinstance(provider, CLIGPSProvider)

    def test_create_cli_provider_with_custom_config(self):
        provider = create_gps_provider(
            "cli",
            command="/custom/gps",
            device="/dev/ttyS0",
            baud=115200,
            timeout=15,
        )
        assert provider.command == "/custom/gps"
        assert provider.device == "/dev/ttyS0"
        assert provider.baud == 115200
        assert provider.timeout == 15

    def test_create_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown GPS provider type"):
            create_gps_provider("unknown")
