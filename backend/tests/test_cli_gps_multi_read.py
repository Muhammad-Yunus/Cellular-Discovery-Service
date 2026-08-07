"""Unit test reproducing the user's exact scenario:

Running `/home/pi/GPS/build/gps -d /dev/ttyAMA0 -b 9600 -w -j` returns multiple
JSON lines. The first few have `has_fix: false` and only later lines get a fix.

Without `-c N`, the GPS tool streams forever. With `-c 5`, we get 5 lines.
The first line(s) are usually `has_fix: false`. The provider must read the
LAST line (which usually has the fix once the device has settled).

This test uses a fake `gps` script that emits multiple JSON lines mimicking
the real device's output behavior.
"""

import json
import os
import subprocess
import stat
import tempfile
import pytest

from app.gps.cli_provider import CLIGPSProvider, GPSReadError


@pytest.fixture
def fake_gps_fix_late():
    """Create a fake `gps` script that prints a few no-fix lines followed by a fix.

    Mirrors the pattern observed when running the real binary against /dev/ttyAMA0:
    first reads return `has_fix: false` until the device acquires a fix.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "gps")
        script = """#!/bin/bash
# Mimic real gps: first N prints have no fix, then a fix appears
echo '{"has_fix": false, "fix_quality": 0, "latitude": 0, "longitude": 0}'
echo '{"has_fix": false, "fix_quality": 0, "latitude": 0, "longitude": 0}'
echo '{"has_fix": true, "fix_quality": 2, "fix_mode": 3, "latitude": -6.150709, "longitude": 106.896840, "altitude_m": 44.9, "satellites_used": 7}'
"""
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        yield path


def test_get_location_picks_fix_from_last_line(fake_gps_fix_late):
    """Provider must return the LAST line if it has a fix.

    User's command: `gps -d /dev/ttyAMA0 -b 9600 -w -j`
    With this flag combo, the real device emits multiple JSON lines. The first
    ones are no-fix; later ones acquire a fix. We pick the last line.
    """
    provider = CLIGPSProvider(
        command=fake_gps_fix_late,
        device="/dev/ttyAMA0",
        baud=9600,
        timeout=10,
        count=3,
    )
    loc = provider.get_location()
    assert loc.latitude == pytest.approx(-6.150709)
    assert loc.longitude == pytest.approx(106.896840)


@pytest.fixture
def fake_gps_no_fix():
    """Fake gps script that emits only no-fix lines."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "gps")
        script = """#!/bin/bash
echo '{"has_fix": false, "fix_quality": 0, "latitude": 0, "longitude": 0}'
echo '{"has_fix": false, "fix_quality": 0, "latitude": 0, "longitude": 0}'
echo '{"has_fix": false, "fix_quality": 0, "latitude": 0, "longitude": 0}'
"""
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        yield path


def test_get_location_no_fix_raises(fake_gps_no_fix):
    """If no line has a fix, raise GPSReadError (with the user's exact message)."""
    provider = CLIGPSProvider(
        command=fake_gps_no_fix,
        device="/dev/ttyAMA0",
        baud=9600,
        timeout=10,
        count=3,
    )
    with pytest.raises(GPSReadError) as exc:
        provider.get_location()
    # The user saw: "No GPS fix. Fix quality: 0"
    assert "No GPS fix" in str(exc.value)


@pytest.fixture
def fake_gps_fix_first():
    """Fake gps script where the first line already has a fix (warm device)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "gps")
        script = """#!/bin/bash
echo '{"has_fix": true, "fix_quality": 2, "fix_mode": 3, "latitude": 1.23, "longitude": 4.56, "altitude_m": 10.0, "satellites_used": 8}'
"""
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        yield path


def test_get_location_fix_first_line(fake_gps_fix_first):
    """If the first line has a fix, return it (warm device case)."""
    provider = CLIGPSProvider(
        command=fake_gps_fix_first,
        device="/dev/ttyAMA0",
        baud=9600,
        timeout=10,
        count=1,
    )
    loc = provider.get_location()
    assert loc.latitude == pytest.approx(1.23)
    assert loc.longitude == pytest.approx(4.56)


@pytest.fixture
def fake_gps_missing_lat_lon():
    """Fake gps script with fix but no lat/lon (degenerate case)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "gps")
        script = """#!/bin/bash
echo '{"has_fix": true, "fix_quality": 2, "fix_mode": 3, "satellites_used": 7}'
"""
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        yield path


def test_get_location_missing_lat_lon_raises(fake_gps_missing_lat_lon):
    """If has_fix=true but lat/lon missing, raise GPSReadError."""
    provider = CLIGPSProvider(
        command=fake_gps_missing_lat_lon,
        device="/dev/ttyAMA0",
        baud=9600,
        timeout=10,
        count=1,
    )
    with pytest.raises(GPSReadError) as exc:
        provider.get_location()
    assert "missing latitude" in str(exc.value).lower() or "latitude" in str(exc.value).lower()
