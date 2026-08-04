import pytest
import subprocess
import json
import shlex


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
              f"fix_mode={data.get('fix_mode', 'N/A')}, "
              f"satellites={data['satellites_used']}")

        # Catatan: GPS bisa butuh time untuk cold start (30s-2 menit)
        if data['has_fix']:
            assert data['fix_quality'] > 0, "Fix quality should be > 0 when has_fix is true"
            assert data['satellites_used'] > 0, "Should see at least 1 satellite"
            assert 'latitude' in data, "Latitude should be present with fix"
            assert 'longitude' in data, "Longitude should be present with fix"

    @pytest.mark.integration
    def test_gps_watch_jq_pattern(self):
        """Test watch mode dengan jq filter (production pattern).
        
        Usage: timeout 60 gps -d /dev/ttyAMA0 -b 9600 -w -j | jq -c 'select(.has_fix==true and .fix_quality>0 and .fix_mode==3)' | head -1
        """
        cmd = (
            f"timeout 30 {self.GPS_CLI} -d {self.GPS_PORT} -b {self.GPS_BAUD} -w -j"
            " | jq -c 'select(.has_fix==true and .fix_quality>0 and .fix_mode==3)'"
            " | head -1"
        )
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=35,
        )
        
        # Command bisa succeed (0) atau timeout (124) - keduanya valid
        # Kita hanya perlu cek output JSON jika ada
        if result.stdout.strip():
            data = json.loads(result.stdout.strip())
            assert data['has_fix'] is True, "GPS should have fix"
            assert data['fix_quality'] > 0, "Fix quality should be > 0"
            assert data['fix_mode'] == 3, "Fix mode should be 3D"
            assert 'latitude' in data, "Latitude should be present"
            assert 'longitude' in data, "Longitude should be present"
            print(f"  GPS Watch Fix: lat={data['latitude']}, lon={data['longitude']}, "
                  f"fix={data['fix_quality']}, mode={data['fix_mode']}, "
                  f"sats={data['satellites_used']}")
        else:
            # Watch mode timeout - GPS belum fix dalam 30s, ini normal
            print("  GPS belum lock dalam 30s (normal untuk cold start)")
            assert result.returncode in [0, 124], f"Unexpected return code: {result.returncode}"

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

    @pytest.mark.integration
    def test_gps_coordinate_accuracy(self):
        """Test akurasi koordinat (harusnya dalam radius tertentu dari expected location)."""
        result = subprocess.run(
            [self.GPS_CLI, "-d", self.GPS_PORT, "-b", str(self.GPS_BAUD), "-j"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        data = json.loads(result.stdout)

        # Skip jika belum lock
        if not data.get('has_fix'):
            pytest.skip("GPS belum lock, skip coordinate accuracy test")

        # Expected: Jakarta area (-6.15, 106.90)
        expected_lat = -6.15
        expected_lon = 106.90
        accuracy_radius_km = 1.0  # Acceptable error: < 1km

        actual_lat = data['latitude']
        actual_lon = data['longitude']

        # Simple distance calculation (Haversine approximation for small distances)
        from math import radians, sin, cos, sqrt, atan2
        R = 6371  # Earth radius in km

        dlat = radians(actual_lat - expected_lat)
        dlon = radians(actual_lon - expected_lon)
        a = sin(dlat/2)**2 + cos(radians(expected_lat)) * cos(radians(actual_lat)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance_km = R * c

        print(f"  Location: ({actual_lat}, {actual_lon}), "
              f"Expected: ({expected_lat}, {expected_lon}), "
              f"Distance: {distance_km:.2f} km")

        assert distance_km < accuracy_radius_km, \
            f"GPS coordinate too far from expected: {distance_km:.2f} km > {accuracy_radius_km} km"

    @pytest.mark.integration
    def test_gps_hdop_quality(self):
        """Test HDOP (Horizontal Dilution of Precision) untuk quality."""
        result = subprocess.run(
            [self.GPS_CLI, "-d", self.GPS_PORT, "-b", str(self.GPS_BAUD), "-j"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        data = json.loads(result.stdout)

        # Skip jika belum lock
        if not data.get('has_fix'):
            pytest.skip("GPS belum lock, skip HDOP test")

        hdop = data.get('hdop', 0)
        print(f"  HDOP: {hdop}")

        # HDOP < 2 = excellent accuracy
        assert hdop < 5, f"HDOP too high: {hdop} (expected < 5 for acceptable accuracy)"
