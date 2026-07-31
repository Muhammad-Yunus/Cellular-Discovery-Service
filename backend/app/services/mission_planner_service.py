from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import MissionLocation
from app.repositories import MissionLocationRepository, MissionRepository
from app.schemas.route import (
    ReorderItem,
    RouteItem,
    RouteResponse,
    SkipResponse,
)
from app.utils.geo import bearing, haversine

ACTIVE_STATUSES = {"STARTING", "RUNNING", "PAUSED"}
MAX_TWO_OPT_PASSES = 100

Point = tuple[float, float, int]


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


class MissionPlannerService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = MissionRepository(db)
        self.location_repo = MissionLocationRepository(db)

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

    def plan(self, mission_id: int) -> RouteResponse:
        mission = self._get_mission_or_404(mission_id)
        self._ensure_inactive(mission, action="plan")

        locs = self.location_repo.get_all_by_mission(mission_id)
        if not locs:
            raise HTTPException(
                status_code=422, detail="Mission has no locations to plan"
            )

        start_idx = 0
        if mission.start_location_id is not None:
            for i, loc in enumerate(locs):
                if loc.id == mission.start_location_id:
                    start_idx = i
                    break

        points = [(loc.latitude, loc.longitude, loc.id) for loc in locs]
        dist_matrix = build_dist_matrix(points)
        index_by_id = {p[2]: i for i, p in enumerate(points)}

        order = nearest_neighbor(points, start_idx)
        order = two_opt(order, dist_matrix, index_by_id)

        ordered_ids = [p[2] for p in order]
        self.location_repo.update_sequence_batch(mission_id, ordered_ids)
        self._write_distances_and_bearings(mission_id, ordered_ids)
        self.repo.update(
            mission, {"status": "READY", "total_locations": len(locs)}
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
