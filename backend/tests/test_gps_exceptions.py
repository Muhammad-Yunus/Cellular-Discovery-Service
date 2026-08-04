"""Tests for GPS exception classes."""
import pytest

from app.gps.exceptions import (
    GPSError,
    GPSNotFoundError,
    GPSReadError,
    GPSTimeoutError,
)


class TestGPSExceptions:
    """Test GPS exception hierarchy."""

    def test_gps_error_base(self):
        """Test base GPSError stores message."""
        exc = GPSError("test error")
        assert exc.message == "test error"
        assert str(exc) == "test error"

    def test_gps_not_found_error_with_device(self):
        """Test GPSNotFoundError includes device in message."""
        exc = GPSNotFoundError("/dev/ttyAMA0")
        assert exc.device == "/dev/ttyAMA0"
        assert "GPS device not found" in str(exc)
        assert "/dev/ttyAMA0" in str(exc)

    def test_gps_not_found_error_no_device(self):
        """Test GPSNotFoundError without device arg."""
        exc = GPSNotFoundError()
        assert exc.device == ""
        assert "GPS device not found" in str(exc)

    def test_gps_read_error_default(self):
        """Test GPSReadError default message."""
        exc = GPSReadError()
        assert "Failed to read GPS data" in str(exc)

    def test_gps_read_error_custom(self):
        """Test GPSReadError with custom message."""
        exc = GPSReadError("bad checksum")
        assert "bad checksum" in str(exc)

    def test_gps_timeout_error_with_timeout(self):
        """Test GPSTimeoutError includes timeout in message."""
        exc = GPSTimeoutError(10)
        assert exc.timeout == 10
        assert "timed out" in str(exc)
        assert "10" in str(exc)

    def test_gps_timeout_error_no_timeout(self):
        """Test GPSTimeoutError without timeout arg."""
        exc = GPSTimeoutError()
        assert exc.timeout == 0
        assert "timed out" in str(exc)

    def test_exceptions_are_catchable_as_gps_error(self):
        """Test all custom exceptions inherit from GPSError."""
        for exc_cls in (GPSNotFoundError, GPSReadError, GPSTimeoutError):
            exc = exc_cls()
            assert isinstance(exc, GPSError)
            assert isinstance(exc, Exception)
