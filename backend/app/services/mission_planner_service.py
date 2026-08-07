import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import MissionLocation
from app.gps import GPSProvider, GPSError
from app.repositories import (
    MissionLocationRepository,
    MissionRepository,
)
from app.schemas.route import (
    ReorderItem,
    RouteItem,
    RouteResponse,
    SkipResponse,
)
from app.utils.geo import bearing, haversine

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"STARTING", "RUNNING", "PAUSED"}
MAX_TWO_OPT_PASSES = 100

Point = tuple[float, float, int]

# Sentinel id used to mark the device-GPS "phantom" node. It can never clash
# with a real MissionLocation.id (which is auto-incremented from 1) and lets
# two_opt / nearest_neighbor treat the device position as just another
# node in the distance matrix without persisting it.
DEVICE_NODE_ID = -1


def build_dist_matrix(points: list[Point]) -> list[list[float]]:
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        lat1, lon1, _ = points[i]
        for j in range(i + 1, n):
            lat2, lon2, _ = points[j]
            d = haversine(lat1, lon1, lat2, lon2)
            matrix[i][j] = matrix[j][i] = d
    return matrix


def nearest_neighbor(points: list[Point], start_idx: int) -> list[Point]:
    """Greedy order: always move to closest unvisited point."""
    n = len(points)
    if n == 0:
        return []
    matrix = build_dist_matrix(points)
    visited = [False] * n
    order = [points[start_idx]]
    visited[start_idx] = True
    current = start_idx
    for _ in range(n - 1):
        best = -1
        best_dist = float("inf")
        for j in range(n):
            if not visited[j]:
                d = matrix[current][j]
                if d < best_dist:
                    best_dist = d
                    best = j
        visited[best] = True
        order.append(points[best])
        current = best
    return order


def two_opt(
    order: list[Point],
    dist_matrix: list[list[float]],
    index_by_id: Optional[dict[int, int]] = None,
) -> list[Point]:
    """Reverse segments whenever it shortens the tour (path, first point fixed)."""
    if index_by_id is None:
        index_by_id = {p[2]: i for i, p in enumerate(order)}
    n = len(order)
    improved = True
    passes = 0
    while improved and passes < MAX_TWO_OPT_PASSES:
        improved = False
        for i in range(1, n - 1):
            for j in range(i, n - 1):
                prev = index_by_id[order[i - 1][2]]
                start = index_by_id[order[i][2]]
                end = index_by_id[order[j][2]]
                nxt = index_by_id[order[j + 1][2]]
                delta = (
                    dist_matrix[prev][end]
                    + dist_matrix[start][nxt]
                    - dist_matrix[prev][start]
                    - dist_matrix[end][nxt]
                )
                if delta < 0:
                    order[i : j + 1] = reversed(order[i : j + 1])
                    improved = True
        passes += 1
    return order


def plan_route_with_origin(
    tower_points: list[Point],
    origin: tuple[float, float],
) -> list[Point]:
    """Run nearest-neighbour + 2-opt with the device's current GPS as the
    tour's starting point.

    The device position is injected as a virtual node (id=DEVICE_NODE_ID)
    at index 0 of the distance matrix. ``nearest_neighbor`` then picks the
    closest tower as the first real visit, and ``two_opt`` is constrained
    so that the device node can never move from position 0 — it acts as a
    fixed origin. The returned list contains only the tower points, in the
    optimal visit order starting from the one closest to ``origin``.

    This solves the "linjer tower" problem: with 5 towers aligned north-to-
    south and the device 2 km east of tower-3, a naive nearest-neighbour
    that picks tower-3 first will still backtrack (3 -> 4 -> 5 -> 2 -> 1)
    because it has no concept of the device being physically off the line.
    Including the device as origin lets the solver choose either
    (3 -> 4 -> 5) or (3 -> 2 -> 1) — whichever yields the shorter leg
    from 3 to the next tower — instead of forcing 3 -> 4.
    """
    if not tower_points:
        return []

    device_point: Point = (origin[0], origin[1], DEVICE_NODE_ID)
    points_with_device = [device_point, *tower_points]
    order_with_device = _plan_tour(points_with_device, origin_idx=0)

    # Drop the device phantom node, keep only real towers.
    return [p for p in order_with_device if p[2] != DEVICE_NODE_ID]


def _plan_tour(points: list[Point], origin_idx: int) -> list[Point]:
    """Nearest-neighbour seeded at ``origin_idx`` + 2-opt with that
    position locked. Works for both:
      * GPS anchor  -> origin_idx=0 is the device phantom node.
      * Manual pin  -> origin_idx=0 is the operator-chosen tower.

    Either way, ``two_opt`` only swaps positions strictly after
    ``origin_idx`` so the fixed root never moves.
    """
    if not points:
        return []
    matrix = build_dist_matrix(points)
    index_by_id = {p[2]: i for i, p in enumerate(points)}
    order = nearest_neighbor(points, origin_idx)

    improved = True
    passes = 0
    while improved and passes < MAX_TWO_OPT_PASSES:
        improved = False
        n = len(order)
        for i in range(origin_idx + 1, n - 1):
            for j in range(i, n - 1):
                prev = index_by_id[order[i - 1][2]]
                start = index_by_id[order[i][2]]
                end = index_by_id[order[j][2]]
                nxt = index_by_id[order[j + 1][2]]
                delta = (
                    matrix[prev][end]
                    + matrix[start][nxt]
                    - matrix[prev][start]
                    - matrix[end][nxt]
                )
                if delta < 0:
                    order[i : j + 1] = reversed(order[i : j + 1])
                    improved = True
        passes += 1
    return order


class MissionPlannerService:
    def __init__(self, db: Session, gps_provider: Optional[GPSProvider] = None):
        """``gps_provider`` is optional for backwards compatibility (e.g.
        reorder / build_route / skip). When ``None``, methods that need GPS
        will raise HTTP 503.
        """
        self.db = db
        self.repo = MissionRepository(db)
        self.location_repo = MissionLocationRepository(db)
        self.gps_provider = gps_provider

    def _get_mission_or_404(self, mission_id: int):
        mission = self.repo.get_by_id(mission_id)
        if not mission:
            raise HTTPException(status_code=404, detail="Mission not found")
        return mission

    def _ensure_inactive(self, mission, action: str = "plan") -> None:
        if mission.status in ACTIVE_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot {action} while mission is {mission.status}",
            )

    @staticmethod
    def _to_route_item(loc) -> RouteItem:
        return RouteItem(
            location_id=loc.id,
            sequence_order=loc.sequence_order,
            cellular_tower_id=loc.cellular_tower_id,
            cellular_tower_name=loc.cellular_tower_name,
            latitude=loc.latitude,
            longitude=loc.longitude,
            status=loc.status,
            distance_from_previous_meters=loc.distance_from_previous_meters,
            bearing_from_previous_degrees=loc.bearing_from_previous_degrees,
            estimated_arrival_time=loc.estimated_arrival_time,
            actual_visit_time=loc.actual_visit_time,
            scan_session_id=loc.scan_session_id,
            visited_at=loc.visited_at,
        )

    def build_route(self, mission_id: int) -> RouteResponse:
        mission = self._get_mission_or_404(mission_id)
        locs = self.location_repo.get_all_by_mission(mission_id)

        planned = sorted(
            [loc for loc in locs if loc.sequence_order is not None],
            key=lambda loc: loc.sequence_order,
        )
        unplanned = sorted(
            [loc for loc in locs if loc.sequence_order is None],
            key=lambda loc: loc.id,
        )

        total_distance = sum(
            loc.distance_from_previous_meters
            for loc in planned
            if loc.distance_from_previous_meters is not None
        )

        return RouteResponse(
            mission_id=mission.id,
            mission_name=mission.name,
            status=mission.status,
            start_location_id=mission.start_location_id,
            total_distance_meters=round(total_distance, 2),
            items=[self._to_route_item(loc) for loc in planned + unplanned],
        )

    def _write_distances_and_bearings(
        self, mission_id: int, ordered_ids: list[int]
    ) -> None:
        locs = self.location_repo.get_all_by_mission(mission_id)
        by_id = {loc.id: loc for loc in locs}

        first = by_id.get(ordered_ids[0])
        if first is not None:
            first.distance_from_previous_meters = None
            first.bearing_from_previous_degrees = None

        for i in range(1, len(ordered_ids)):
            prev = by_id[ordered_ids[i - 1]]
            cur = by_id[ordered_ids[i]]
            cur.distance_from_previous_meters = round(
                haversine(
                    prev.latitude, prev.longitude, cur.latitude, cur.longitude
                ),
                2,
            )
            cur.bearing_from_previous_degrees = round(
                bearing(
                    prev.latitude, prev.longitude, cur.latitude, cur.longitude
                ),
                2,
            )

        self.db.commit()

    def _get_device_gps_or_503(self) -> tuple[float, float]:
        """Read GPS coordinates directly from the configured provider.

        Raises HTTP 503 when no provider is wired or the device returns no
        fix. We intentionally do NOT consult ``scan_sessions``: the latest
        scan's GPS may be many minutes old by the time /plan is called, and
        the operator's device may have moved in the meantime.
        """
        if self.gps_provider is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "GPS provider not configured. Cannot determine "
                    "starting position for route optimisation."
                ),
            )

        try:
            location = self.gps_provider.get_location()
        except GPSError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"GPS provider error: {exc}",
            ) from exc

        if location is None or not location.latitude or not location.longitude:
            raise HTTPException(
                status_code=400,
                detail=(
                    "GPS fix not available. Cannot optimise route from "
                    "an unknown device position."
                ),
            )

        return (location.latitude, location.longitude)

    def plan(self, mission_id: int) -> RouteResponse:
        mission = self._get_mission_or_404(mission_id)
        self._ensure_inactive(mission, action="plan")

        locs = self.location_repo.get_all_by_mission(mission_id)
        if not locs:
            raise HTTPException(
                status_code=422, detail="Mission has no locations to plan"
            )

        points = [(loc.latitude, loc.longitude, loc.id) for loc in locs]

        # Two optimisation paths:
        #
        # A) Manual start_location_id set  ->  the operator pinned a fixed
        #    tower. Respect it. We still use GPS-aware nearest-neighbour for
        #    the *remainder* of the tour so the operator gets the best
        #    possible route starting from their pinned tower.
        #
        # B) No manual override  ->  get a live GPS fix from the device,
        #    inject it as the tour origin, and let nearest-neighbour pick
        #    the best first tower and 2-opt polish the rest.
        if mission.start_location_id is not None:
            start_idx: Optional[int] = None
            for i, loc in enumerate(locs):
                if loc.id == mission.start_location_id:
                    start_idx = i
                    break
            if start_idx is None:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"start_location_id={mission.start_location_id} "
                        "does not belong to this mission"
                    ),
                )

            pinned = points[start_idx]
            others = [p for i, p in enumerate(points) if i != start_idx]
            # NN seeded at the pinned tower (position 0) so the manual
            # pin is respected. 2-opt is constrained to only swap within
            # the remaining N-1 positions, so the pinned tower never
            # leaves position 0.
            order = _plan_tour([pinned, *others], origin_idx=0)
            logger.info(
                "plan(mid=%s): manual start tower id=%s, optimised route "
                "for remaining towers (no GPS needed for fixed pin)",
                mission_id,
                pinned[2],
            )
        else:
            device_lat, device_lon = self._get_device_gps_or_503()
            device_origin = (device_lat, device_lon)
            order = plan_route_with_origin(points, device_origin)
            logger.info(
                "plan(mid=%s): GPS-origin NN-2opt, device at (%.5f,%.5f), "
                "first tower id=%s",
                mission_id,
                device_lat,
                device_lon,
                order[0][2] if order else None,
            )

        ordered_ids = [p[2] for p in order]
        self.location_repo.update_sequence_batch(mission_id, ordered_ids)
        self._write_distances_and_bearings(mission_id, ordered_ids)
        self.repo.update(
            mission,
            {
                "status": "READY",
                "total_locations": len(locs),
                "start_location_id": ordered_ids[0],
            },
        )

        return self.build_route(mission_id)

    def reorder(
        self, mission_id: int, payload: list[ReorderItem]
    ) -> RouteResponse:
        mission = self._get_mission_or_404(mission_id)
        self._ensure_inactive(mission, action="reorder")

        if not payload:
            raise HTTPException(
                status_code=422, detail="Reorder list cannot be empty"
            )

        existing = {
            loc.id for loc in self.location_repo.get_all_by_mission(mission_id)
        }
        submitted = {item.location_id for item in payload}

        foreign = sorted(submitted - existing)
        if foreign:
            raise HTTPException(
                status_code=422,
                detail=f"location_id {foreign[0]} does not belong to this mission",
            )

        missing = sorted(existing - submitted)
        if missing:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Reorder list must include all mission locations. "
                    f"Missing: {missing}"
                ),
            )

        orders = [item.sequence_order for item in payload]
        if len(orders) != len(set(orders)):
            raise HTTPException(
                status_code=422,
                detail="Duplicate sequence_order values are not allowed",
            )

        ordered_ids = [
            item.location_id
            for item in sorted(payload, key=lambda item: item.sequence_order)
        ]
        self.location_repo.update_sequence_batch(mission_id, ordered_ids)
        self._write_distances_and_bearings(mission_id, ordered_ids)
        self.repo.update(mission, {"status": "READY"})

        return self.build_route(mission_id)

    def skip(self, mission_id: int, location_id: int) -> SkipResponse:
        mission = self._get_mission_or_404(mission_id)
        self._ensure_inactive(mission, action="skip")

        loc = self.location_repo.get_by_mission_and_id(mission_id, location_id)
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")

        self.location_repo.mark_skipped(mission_id, location_id)

        remaining = sorted(
            [
                item
                for item in self.location_repo.get_all_by_mission(mission_id)
                if item.id != location_id and item.sequence_order is not None
            ],
            key=lambda item: item.sequence_order,
        )
        for idx, item in enumerate(remaining, start=1):
            item.sequence_order = idx
        ordered_ids = [item.id for item in remaining]
        if ordered_ids:
            self._write_distances_and_bearings(mission_id, ordered_ids)
        else:
            self.db.commit()

        return SkipResponse(
            message="Location skipped successfully", location_id=location_id
        )