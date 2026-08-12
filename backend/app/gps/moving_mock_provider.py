"""Moving mock GPS provider for simulated drone tours.

Returns continuously moving fake GPS coordinates that simulate a drone
flying from the start location through a sequence of waypoints (towers),
loitering 2-3 times within the mission radius at each tower before
proceeding to the next waypoint, and finally returning to the start.

Usage:
    GPS_PROVIDER=moving_mock
    MOCK_GPS_START_LAT=-6.150677
    MOCK_GPS_START_LON=106.896652
    MOCK_GPS_WAYPOINTS=-6.18,106.83:-6.17,106.84  # colon-separated lat,lon pairs
    MOCK_GPS_LOITER_RADIUS=20  # meters
    MOCK_GPS_SPEED_MS=10       # meters per second (drone cruise speed)
    MOCK_GPS_LOITER_LAPS=3     # circles per waypoint
"""

import math
import time
import threading
from app.gps.schemas import GPSLocation
from app.gps.provider import GPSProvider


class MovingMockGPSProvider(GPSProvider):
    """Simulates realistic drone movement through waypoints.

    Movement model:
    1. Start at MOCK_GPS_START_LAT/LON
    2. For each waypoint (tower):
       - Fly from current position to waypoint at cruise speed
       - Loiter (circle) 2-3 times within radius around the waypoint
       - Move to next waypoint
    3. After last waypoint: fly back to start
    """

    def __init__(
        self,
        start_lat: float = -6.150677,
        start_lon: float = 106.896652,
        waypoints: list[tuple[float, float]] | None = None,
        loiter_radius_m: float = 20.0,
        cruise_speed_ms: float = 50.0,  # 50 m/s = 180 km/h, fast for testing
        loiter_laps: int = 3,
        altitude_m: float = 100.0,  # Fixed altitude for drone simulation
    ):
        self._start = (start_lat, start_lon)
        self._waypoints = waypoints or []
        self._loiter_radius_m = loiter_radius_m
        self._cruise_speed_ms = cruise_speed_ms
        self._loiter_laps = loiter_laps
        self._altitude_m = altitude_m

        # Build full path: start -> waypoints -> start
        self._path = [self._start] + list(self._waypoints) + [self._start]

        # Precompute segment distances (meters) and ETAs (seconds)
        self._segment_distances = []
        self._segment_durations = []
        for i in range(len(self._path) - 1):
            d = self._haversine_m(self._path[i], self._path[i + 1])
            self._segment_distances.append(d)
            # Add 2s loiter time at the end of each segment (except final return)
            if i < len(self._path) - 2:
                dur = d / self._cruise_speed_ms + self._loiter_duration_s()
            else:
                dur = d / self._cruise_speed_ms
            self._segment_durations.append(dur)

        self._total_duration = sum(self._segment_durations)

        self._lock = threading.Lock()
        self._start_time = time.time()
        self._last_position = None
        self._last_timestamp = None

    def _loiter_duration_s(self) -> float:
        """Time for `loiter_laps` circles at radius with angular speed.

        A circle of radius R has circumference 2*pi*R. We pick angular speed
        such that one lap takes ~loiter_laps seconds (so 2.5 laps = 2.5s).
        """
        circumference_m = 2 * math.pi * self._loiter_radius_m
        # 1 lap per 1.5s so loiter_laps=3 → 4.5s of loiter time
        seconds_per_lap = 1.5
        return self._loiter_laps * seconds_per_lap

    @staticmethod
    def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
        """Distance in meters between two lat/lon points."""
        R = 6371000.0
        lat1, lon1 = math.radians(a[0]), math.radians(a[1])
        lat2, lon2 = math.radians(b[0]), math.radians(b[1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * R * math.asin(math.sqrt(h))

    def _interpolate(
        self, a: tuple[float, float], b: tuple[float, float], t: float
    ) -> tuple[float, float]:
        """Linear interpolation between two coords (good enough for short legs)."""
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    def _offset_circle(
        self, center: tuple[float, float], angle: float, radius_m: float
    ) -> tuple[float, float]:
        """Position on a circle of `radius_m` meters around `center`.

        angle=0 is due north; increases clockwise (compass-style).
        """
        # Convert meters to degrees latitude (1 deg lat ≈ 111320 m)
        lat_offset = (radius_m * math.cos(angle)) / 111320.0
        # Convert meters to degrees longitude (depends on latitude)
        lon_scale = 111320.0 * math.cos(math.radians(center[0]))
        lon_offset = (radius_m * math.sin(angle)) / max(lon_scale, 1e-6)
        return (center[0] + lat_offset, center[1] + lon_offset)

    def _bearing_to_waypoint(self, from_pos: tuple[float, float], to_pos: tuple[float, float]) -> float:
        """Calculate bearing from current position to target position in degrees."""
        lat1, lon1 = math.radians(from_pos[0]), math.radians(from_pos[1])
        lat2, lon2 = math.radians(to_pos[0]), math.radians(to_pos[1])
        dlon = lon2 - lon1
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360) % 360

    def get_location(self) -> GPSLocation:
        """Return simulated drone position with altitude, course, and speed."""
        import datetime
        with self._lock:
            elapsed = time.time() - self._start_time
            # Loop the tour forever
            elapsed = elapsed % max(self._total_duration, 1.0)

            # Find which segment we're in
            acc = 0.0
            for i, dur in enumerate(self._segment_durations):
                if elapsed < acc + dur:
                    seg_t = elapsed - acc  # time within this segment
                    start = self._path[i]
                    end = self._path[i + 1]

                    fly_duration = (
                        self._segment_distances[i] / self._cruise_speed_ms
                    )
                    if seg_t < fly_duration:
                        # Still flying to next waypoint
                        t = seg_t / max(fly_duration, 1e-6)
                        pos = self._interpolate(start, end, t)
                    else:
                        # Loitering at end of segment (waypoint)
                        loiter_t = seg_t - fly_duration
                        loiter_total = self._loiter_duration_s()
                        # 2*pi per lap, 1 lap per 1.5s
                        angle_per_sec = (2 * math.pi) / 1.5
                        angle = (loiter_t * angle_per_sec) % (2 * math.pi)
                        pos = self._offset_circle(end, angle, self._loiter_radius_m)
                    break
                acc += dur
            else:
                # Past last segment (shouldn't happen with mod)
                pos = self._path[-1]

            # Calculate course and speed
            now = datetime.datetime.now()
            current_time = now.timestamp()

            if self._last_position is not None:
                dist = self._haversine_m(self._last_position, pos)
                time_diff = current_time - self._last_timestamp
                if time_diff > 0:
                    speed = dist / time_diff
                    course = self._bearing_to_waypoint(self._last_position, pos)
                else:
                    speed = 0.0
                    course = 0.0
            else:
                # First call - use bearing from start to first position
                speed = 0.0
                course = self._bearing_to_waypoint(self._start, pos) if self._start != pos else 0.0

            # Update tracking
            self._last_position = pos
            self._last_timestamp = current_time

            return GPSLocation(
                latitude=pos[0],
                longitude=pos[1],
                altitude=self._altitude_m,
                course_deg=round(course, 2),
            )

    def is_available(self) -> bool:
        return True
