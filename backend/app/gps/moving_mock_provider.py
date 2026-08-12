"""Moving mock GPS provider for simulated drone tours.

Returns continuously moving fake GPS coordinates that simulate a drone
flying from the start location through waypoints (towers), loitering
exactly 3 laps at each tower within the mission radius, then exiting
the mission radius before proceeding to the next tower, and finally
returning to the start position.

Movement model (per tower):
1. Fly from current position to tower (approach)
2. Loiter (circle) exactly `loiter_laps` times within `loiter_radius_m`
3. Exit: fly outward beyond the mission radius (to clear the geofence)
4. Mark as visited (handled by mission_executor based on scan count)
5. Proceed to next tower
6. After last tower: fly back to start

Usage:
    GPS_PROVIDER=moving_mock
    MOCK_GPS_START_LAT=-6.150677
    MOCK_GPS_START_LON=106.896652
    MOCK_GPS_WAYPOINTS=-6.146148,106.897008:-6.148741,106.902901
    MOCK_GPS_LOITER_RADIUS_M=20   # meters (must match mission radius)
    MOCK_GPS_SPEED_MS=40          # meters per second
    MOCK_GPS_LOITER_LAPS=3        # circles per waypoint
    MOCK_GPS_START_OFFSET=0       # seconds to offset start (negative = delayed)
"""

import math
import time
import logging
import threading
from app.gps.schemas import GPSLocation
from app.gps.provider import GPSProvider

logger = logging.getLogger(__name__)

# ============================================================================
# Helper functions
# ============================================================================


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance in meters between two lat/lon points."""
    R = 6371000.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def _bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Bearing from point a to point b in degrees (0=North, clockwise)."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = (math.cos(lat1) * math.sin(lat2) -
         math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def _offset_by_bearing(
    center: tuple[float, float], bearing_deg: float, distance_m: float
) -> tuple[float, float]:
    """Offset a point by bearing and distance (meters), result in (lat, lon)."""
    R = 6371000.0
    lat1, lon1 = math.radians(center[0]), math.radians(center[1])
    bearing_rad = math.radians(bearing_deg)
    d = distance_m / R

    lat2 = math.asin(math.sin(lat1) * math.cos(d) +
                     math.cos(lat1) * math.sin(d) * math.cos(bearing_rad))
    lon2 = lon1 + math.atan2(
        math.sin(bearing_rad) * math.sin(d) * math.cos(lat1),
        math.cos(d) - math.sin(lat1) * math.sin(lat2)
    )
    return (math.degrees(lat2), math.degrees(lon2))


def _circle_offset(
    center: tuple[float, float], angle_rad: float, radius_m: float
) -> tuple[float, float]:
    """Position on a circle of `radius_m` meters around `center`.

    angle=0 is due north; increases clockwise.
    """
    lat_offset = (radius_m * math.cos(angle_rad)) / 111320.0
    lon_scale = 111320.0 * math.cos(math.radians(center[0]))
    lon_offset = (radius_m * math.sin(angle_rad)) / max(abs(lon_scale), 1e-6)
    return (center[0] + lat_offset, center[1] + lon_offset)


def _linear_interp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    """Linear interpolation between two coords (short distances)."""
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


# ============================================================================
# Provider class
# ============================================================================


class MovingMockGPSProvider(GPSProvider):
    """Simulates realistic drone movement through waypoints.

    Path sequence for each tower:
      [approach] Fly toward tower
      [loiter]   Circle exactly `loiter_laps` times inside mission radius
      [exit]     Fly outward past the mission radius
    After last tower:
      [return]   Fly back to start
    Then loop forever.
    """

    def __init__(
        self,
        start_lat: float = -6.150677,
        start_lon: float = 106.896652,
        waypoints: list[tuple[float, float]] | None = None,
        loiter_radius_m: float = 20.0,
        cruise_speed_ms: float = 50.0,
        loiter_laps: int = 3,
        altitude_m: float = 100.0,
        start_offset: float = 0.0,
    ):
        self._start = (start_lat, start_lon)
        self._waypoints = list(waypoints) if waypoints else []
        self._loiter_radius_m = max(loiter_radius_m, 1.0)
        self._cruise_speed_ms = max(cruise_speed_ms, 1.0)
        self._loiter_laps = max(loiter_laps, 1)
        self._altitude_m = altitude_m
        self._start_offset = start_offset

        # Build structured path with explicit phases
        self._path = self._build_path()
        self._segments = self._build_segments()
        self._total_duration = sum(s["duration_s"] for s in self._segments)

        # Trace state
        self._lock = threading.Lock()
        self._start_time = time.time() + start_offset
        self._last_position: tuple[float, float] | None = None
        self._last_timestamp: float | None = None
        self._last_phase: str | None = None  # for change-detect logging

    # ------------------------------------------------------------------
    # Path construction
    # ------------------------------------------------------------------

    def _build_path(self) -> list[tuple[float, float]]:
        """Build the tour path with explicit approach / loiter / exit phases.

        Each tower gets:
          - approach_point : waypoint itself  (destination of approach leg)
          - loiter_point   : same as waypoint (center of circle)
          - exit_point     : 1.5× radius beyond waypoint, along approach bearing

        Final segment flies back to start.
        """
        if not self._waypoints:
            # No waypoints: just fly in a small circle at start and back
            return [self._start, self._start]

        path: list[tuple[float, float]] = [self._start]

        for i, tower in enumerate(self._waypoints):
            # Approach phase: destination = tower
            path.append(tower)

            # Exit phase: fly outward from tower, away from previous position
            if i == 0:
                prev = self._start
            else:
                prev = self._waypoints[i - 1]

            exit_bearing = _bearing(prev, tower)
            exit_point = _offset_by_bearing(
                tower, exit_bearing, self._loiter_radius_m * 1.5
            )
            path.append(exit_point)

        # Return to start
        path.append(self._start)
        return path

    def _build_segments(self) -> list[dict]:
        """Compute durations and labels for every path segment.

        Path structure: [start, tower0, exit0, tower1, exit1, ..., start]

        Each tower has 3 phases:
          - approach: fly TO the tower
          - loiter:   circle at the tower (inserted separately)
          - exit:     fly AWAY from the tower (past mission radius)
        Last leg: fly back to start.
        """
        segments: list[dict] = []
        n_waypoints = len(self._waypoints)

        for i in range(len(self._path) - 1):
            a, b = self._path[i], self._path[i + 1]
            dist = _haversine_m(a, b)
            dur = dist / self._cruise_speed_ms

            # Label segments based on their role
            if i == 0:
                # First leg: start -> tower0
                phase_type = "approach_tower_0"
            elif i == len(self._path) - 2:
                # Last leg: exit_{n-1} -> start
                phase_type = "return_to_start"
            elif i % 2 == 1:
                # Odd index after first: tower_k -> exit_k
                phase_type = f"exit_tower_{(i - 1) // 2}"
            else:
                # Even index after first: exit_{k} -> tower_{k+1}
                phase_type = f"approach_tower_{i // 2}"

            segments.append({
                "type": phase_type,
                "start": a,
                "end": b,
                "distance_m": dist,
                "duration_s": dur,
            })

        # Insert loiter segments after each approach segment
        result: list[dict] = []
        seg_idx = 0
        for tower_idx in range(n_waypoints):
            # Find the approach segment ending at this tower
            while seg_idx < len(segments) and segments[seg_idx]["end"] != self._waypoints[tower_idx]:
                result.append(segments[seg_idx])
                seg_idx += 1
            if seg_idx >= len(segments):
                break
            # Add the approach segment
            result.append(segments[seg_idx])
            seg_idx += 1
            # Insert loiter segment at this tower
            result.append({
                "type": "loiter",
                "center": self._waypoints[tower_idx],
                "radius_m": self._loiter_radius_m,
                "duration_s": self._loiter_duration_s(),
                "distance_m": 2 * math.pi * self._loiter_radius_m,
            })

        # Append remaining segments (exits + return)
        for s in segments[seg_idx:]:
            result.append(s)

        return result

    # ------------------------------------------------------------------
    # Timing helpers
    # ------------------------------------------------------------------

    def _loiter_duration_s(self) -> float:
        """Time for `loiter_laps` complete circles at `loiter_radius_m`.

        Speed around the circle = cruise_speed_ms, so:
            duration = (circumference × laps) / speed
        """
        circumference = 2 * math.pi * self._loiter_radius_m
        return (circumference * self._loiter_laps) / self._cruise_speed_ms

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset_start_time(self) -> None:
        """Reset the internal timer. Call when mission actually starts
        so that the trajectory begins from t=0 rather than from provider init."""
        with self._lock:
            self._start_time = time.time()

    def get_location(self) -> GPSLocation:
        """Return simulated GPS position with altitude and course."""
        import datetime

        with self._lock:
            elapsed = time.time() - self._start_time
            elapsed = elapsed % max(self._total_duration, 1e-6)

            acc = 0.0
            pos = self._start
            course = 0.0
            current_phase = "unknown"

            for seg in self._segments:
                seg_dur = seg["duration_s"]
                if elapsed < acc + seg_dur:
                    seg_t = elapsed - acc
                    current_phase = seg["type"]

                    if seg["type"] == "loiter":
                        # Circular motion around waypoint
                        center = seg["center"]
                        radius = seg["radius_m"]
                        # One full revolution = seg_dur seconds
                        angular_speed = (2 * math.pi) / seg_dur
                        angle_rad = (seg_t * angular_speed) % (2 * math.pi)
                        pos = _circle_offset(center, angle_rad, radius)
                        course = _bearing(center, pos)
                    else:
                        # Linear interpolation along approach / exit / return
                        t = seg_t / max(seg_dur, 1e-6)
                        pos = _linear_interp(seg["start"], seg["end"], t)
                        course = _bearing(seg["start"], seg["end"])
                    break
                acc += seg_dur
            else:
                pos = self._start

            # Speed / course from last known position
            now = datetime.datetime.now()
            current_time = now.timestamp()

            if self._last_position is not None:
                dist = _haversine_m(self._last_position, pos)
                time_diff = current_time - (self._last_timestamp or current_time)
                speed = dist / max(time_diff, 1e-6)
                course = _bearing(self._last_position, pos)
            else:
                speed = 0.0
                course = _bearing(self._start, pos)

            # Phase-change trace log
            if self._last_phase != current_phase:
                logger.info(
                    f"[GPS] Phase={current_phase}  pos=({pos[0]:.6f}, {pos[1]:.6f})"
                )
                self._last_phase = current_phase

            self._last_position = pos
            self._last_timestamp = current_time

            return GPSLocation(
                latitude=pos[0],
                longitude=pos[1],
                altitude=self._altitude_m,
                course_deg=round(course, 2),
            )

    @property
    def total_duration(self) -> float:
        return self._total_duration

    @property
    def segments_summary(self) -> list[dict]:
        return [
            {
                "type": s["type"],
                "distance_m": round(s.get("distance_m", 0), 1),
                "duration_s": round(s["duration_s"], 2),
            }
            for s in self._segments
        ]

    def is_available(self) -> bool:
        return True
