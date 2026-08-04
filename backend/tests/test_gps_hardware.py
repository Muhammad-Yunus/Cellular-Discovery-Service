import pytest
import subprocess
import json


class TestGPSHardwareIntegration:
    """Integration tests untuk GPS hardware U-blox M6 di /dev/ttyAMA0."""

    GPS_CLI = "/home/pi/GPS/build/gps"
    GPS_PORT = "/dev/ttyAMA0"
    GPS_BAUD = 9600

    @pytest.mark.integration
    def test_gps_cli_executable_exists(self):
        """Verify CLI tool bisa di-execute."""
        import os
        assert os.path.isfile(self.GPS_CLI), f"GPS CLI not found: {self.GPS_CLI}"
        assert os.access(self.GPS_CLI, os.X_OK), f"GPS CLI not executable: {self.GPS_CLI}"

    @pytest.mark.integration
    def test_gps_port_exists(self):
        """Verify /dev/ttyAMA0 tersedia."""
        import os
        assert os.path.exists(self.GPS_PORT), f"GPS port not found: {self.GPS_PORT}"

    @pytest.mark.integration
    def test_gps_cli_basic_output(self):
        """Test CLI command bisa jalan dan output JSON valid."""
        result = subprocess.run(
            [self.GPS_CLI, "-d", self.GPS_PORT, "-b", str(self.GPS_BAUD), "-j"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, f"GPS CLI failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert "has_fix" in data
        assert "fix_quality" in data
        assert "satellites_used" in data

    @pytest.mark.integration
    def test_gps_fix_status(self):
        """Test apakah GPS sudah lock (fix)."""
        result = subprocess.run(
            [self.GPS_CLI, "-d", self.GPS_PORT, "-b", str(self.GPS_BAUD), "-j"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        data = json.loads(result.stdout)

        print(f"  GPS Status: has_fix={data['has_fix']}, "
              f"fix_quality={data['fix_quality']}, "
              f"satellites={data['satellites_used']}")

        # Catatan: GPS bisa butuh time untuk cold start (30s-2 menit)
        if data['has_fix']:
            assert data['fix_quality'] > 0, "Fix quality should be > 0 when has_fix is true"
            assert data['satellites_used'] > 0, "Should see at least 1 satellite"
            assert 'latitude' in data, "Latitude should be present with fix"
            assert 'longitude' in data, "Longitude should be present with fix"

    @pytest.mark.integration
    def test_gps_cli_formatted_output(self):
        """Test CLI formatted output (tanpa -j flag)."""
        result = subprocess.run(
            [self.GPS_CLI, "-d", self.GPS_PORT, "-b", str(self.GPS_BAUD)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout
        assert len(output) > 0, "Should receive GPS output"
        # CLI menampilkan formatted text status
        assert "GPS Status" in output or "Fix:" in output or "Satellites" in output, \
            f"Expected formatted GPS output, got: {output[:200]}"

    @pytest.mark.integration
    def test_gps_multiple_reads_consistency(self):
        """Test beberapa bacaan GPS memberikan hasil konsisten."""
        readings = []
        for i in range(3):
            result = subprocess.run(
                [self.GPS_CLI, "-d", self.GPS_PORT, "-b", str(self.GPS_BAUD), "-j"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            data = json.loads(result.stdout)
            readings.append(data)

        # Semua bacaan harus punya has_fix yang sama
        fixes = [r['has_fix'] for r in readings]
        assert len(set(fixes)) <= 1, "GPS fix status should be consistent across reads"
