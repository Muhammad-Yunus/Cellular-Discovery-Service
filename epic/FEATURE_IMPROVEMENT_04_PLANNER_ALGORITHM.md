# FEATURE_IMPROVEMENT_04_PLANNER_ALGORITHM.md

> Mission Planner Epic — Phase 4: Planner Algorithm (Auto-Plan & Manual Route Reorder)

| Field | Value |
|-------|-------|
| **Epic** | Mission Planner (epic/) |
| **Phase** | 4 of 10 |
| **Dependencies** | [02_LOCATION_MANAGEMENT](FEATURE_IMPROVEMENT_02_LOCATION_MANAGEMENT.md), [03_MISSION_CRUD](FEATURE_IMPROVEMENT_03_MISSION_CRUD.md) |
| **Estimated LOC** | ~420 |
| **Complexity** | High |
| **Status** | Draft |
| **Target** | Dev backend at `~/Cellular-Discovery-Service/backend` |

---

## 📑 Table of Contents

1. [Goals](#1-goals)
2. [Backend Tasks](#2-backend-tasks)
3. [File Changes](#3-file-changes)
4. [API Specs](#4-api-specs)
5. [Business Logic Specs](#5-business-logic-specs)
6. [Acceptance Criteria](#6-acceptance-criteria)

---

## 1. Goals

- Provide **auto-planning** (`POST /{id}/plan`): Nearest-Neighbor from start location, then **2-opt** refinement; writes `sequence_order`, `distance_from_previous_meters`, `bearing_from_previous_degrees` onto `mission_locations`.
- Provide **manual route override** (`POST /{id}/route/reorder`) and **skip** (`POST /{id}/route/skip`).
- Provide **route readback** (`GET /{id}/route`) ordered by `sequence_order`.
- Manage planning status transitions: `IDLE` → `PLANNING` → `READY` (re-plan allowed from `STOPPED`/`FAILED` → `PLANNING` → `READY`). Planning is only allowed while mission is not active.
- Add pure utility module `app/utils/geo.py` (haversine + bearing) — no external dependencies (stdlib math only).

---

## 2. Backend Tasks

1. [ ] Create `backend/app/utils/geo.py` — `haversine`, `bearing`.
2. [ ] Add repository methods to `MissionLocationRepository` (Phase 2 file):
   - `get_all_by_mission(mission_id)` → all rows ordered by `id`.
   - `update_sequence_batch(mission_id, ordered_ids)` → sets `sequence_order` (1-based); **preserves `VISITED` rows** (status + `scan_session_id`/visit fields) and resets all other rows to `PENDING`, clearing their visit fields (re-plan of a `STOPPED`/`FAILED` mission keeps completed visits — Edge E22).
   - `clear_sequence_order(mission_id)` → sets `sequence_order = NULL` (already referenced in Phase 3).
   - `get_by_mission_and_id(mission_id, location_id)` → single row or None.
   - `mark_skipped(mission_id, location_id)` → `status='SKIPPED'`.
3. [ ] Create `app/schemas/route.py` — `RouteItem`, `RouteResponse`, `ReorderRequest`, `ReorderItem`, `SkipResponse`.
4. [ ] Create `app/services/mission_planner_service.py` — Nearest-Neighbor + 2-opt + orchestration.
5. [ ] Create `app/api/routers/mission_planning.py` — `/api/v1/missions/{id}/plan`, `/route`, `/route/reorder`, `/route/skip`.
6. [ ] Register router in `app/main.py` (same prefix `/api/v1/missions`).
7. [ ] Write unit + integration tests.
8. [ ] Run full test suite (no regressions).

---

## 3. File Changes

### New files
| Path | Description |
|------|-------------|
| `backend/app/utils/geo.py` | `haversine`, `bearing` (pure functions, stdlib only) |
| `backend/app/schemas/route.py` | Route / reorder / skip Pydantic models |
| `backend/app/services/mission_planner_service.py` | NN + 2-opt algorithm + service logic |
| `backend/app/api/routers/mission_planning.py` | Plan / route / reorder / skip endpoints |

### Modified files
| Path | Description |
|------|-------------|
| `backend/app/repositories/mission_location_repository.py` | Add 5 methods from task 2 |
| `backend/app/main.py` | Include `mission_planning` router |
| `backend/app/schemas/__init__.py` | Export route schemas |
| `backend/app/services/__init__.py` | Export `MissionPlannerService` |
| `backend/tests/` | New `tests/test_geo.py`, `tests/test_planning.py` |

---

## 4. API Specs

### 4.1 `POST /api/v1/missions/{mission_id}/plan`

Generate auto-plan (Nearest-Neighbor + 2-opt).

**Allowed mission status:** `IDLE`, `PLANNING`, `READY`, `STOPPED`, `FAILED` (all non-active; re-plan from `STOPPED`/`FAILED` resets → `PLANNING` → `READY`). Active (`STARTING`/`RUNNING`/`PAUSED`) → `409 Conflict: Cannot plan while mission is <status>`.

**Behavior:**
1. Load all locations of the mission (`get_all_by_mission`).
2. If none → `422: Mission has no locations to plan`.
3. Start point = `mission.start_location_id` if set, else the first location by `id`.
4. Run Nearest-Neighbor from start; refine with 2-opt.
5. Write `sequence_order` (1-based). **Preserve `VISITED` rows** (status, `scan_session_id`, `actual_visit_time`, `visited_at` stay); reset all other rows (`PENDING`/`IN_PROGRESS`/`SKIPPED`) to `PENDING` and clear `scan_session_id`/`actual_visit_time`/`visited_at`/`distance`/`bearing`/`estimated_arrival_time` on them (re-plan of a `STOPPED`/`FAILED` mission keeps completed visits — Edge E22).
6. Compute `distance_from_previous_meters` + `bearing_from_previous_degrees` per row (first in sequence: `NULL`).
7. `mission.status = 'READY'`, `mission.total_locations` re-synced.

**Response:** `200` → `RouteResponse` (see 4.2). · `404` → `Mission not found`. · `422` → no locations. · `409` → active.

### 4.2 `GET /api/v1/missions/{mission_id}/route`

**Response:**
```json
{
  "mission_id": 3,
  "mission_name": "Jakarta Utara Sweep",
  "status": "READY",
  "start_location_id": 5,
  "total_distance_meters": 8423.5,
  "items": [
    {
      "location_id": 5,
      "sequence_order": 1,
      "cellular_tower_id": "TWR-005",
      "cellular_tower_name": "Jakarta Pusat",
      "latitude": -6.2088,
      "longitude": 106.8456,
      "status": "PENDING",
      "distance_from_previous_meters": null,
      "bearing_from_previous_degrees": null,
      "estimated_arrival_time": null,
      "actual_visit_time": null,
      "scan_session_id": null,
      "visited_at": null
    },
    {
      "location_id": 9,
      "sequence_order": 2,
      "cellular_tower_id": "TWR-009",
      "cellular_tower_name": "Jakarta Selatan",
      "latitude": -6.2615,
      "longitude": 106.8106,
      "status": "PENDING",
      "distance_from_previous_meters": 4821.2,
      "bearing_from_previous_degrees": 187.4,
      "estimated_arrival_time": null,
      "actual_visit_time": null,
      "scan_session_id": null,
      "visited_at": null
    }
  ]
}
```

- Items with `sequence_order IS NULL` (unplanned) listed **after** planned ones, sorted by `id`.
- `total_distance_meters` = sum of `distance_from_previous_meters` over planned items (0 if none).

`404` → `Mission not found`.

### 4.3 `POST /api/v1/missions/{mission_id}/route/reorder`

Manual override. Payload is a **complete** ordered list of the mission's locations.

**Request body:**
```json
[
  {"location_id": 9, "sequence_order": 1},
  {"location_id": 5, "sequence_order": 2},
  {"location_id": 7, "sequence_order": 3}
]
```

**Validation:**
- Array must be non-empty → `422: Reorder list cannot be empty`.
- Every `location_id` must belong to the mission → `422: location_id <id> does not belong to this mission`.
- The set of `location_id`s must exactly match the mission's current location set → `422: Reorder list must include all mission locations`.
- `sequence_order` values must be unique → `422: Duplicate sequence_order: <n>`.
- `sequence_order` will be re-indexed 1..N in given order (input numbers are relative order, not absolute).

**Behavior:** overwrites `sequence_order`, recomputes distance/bearing, **preserves `VISITED` rows** (status + visit fields), resets all other rows to `PENDING` (skipped locations stay `SKIPPED` only if re-skipped via skip endpoint; otherwise reorder resets non-visited to `PENDING`), clears visit fields on non-visited rows only, keeps `mission.status = 'READY'`.

**Responses:** `200` → `RouteResponse`. · `404` → `Mission not found`. · `409` → active. · `422` → validation.

> Manual override takes precedence over auto-plan. Any later auto-plan call fully replaces the order.

### 4.4 `POST /api/v1/missions/{mission_id}/route/skip`

Mark a single location as skipped (executor will ignore it).

**Request body:**
```json
{"location_id": 7}
```

**Behavior:**
- Sets `status='SKIPPED'`, `sequence_order` becomes `NULL`, clears distance/bearing/visit fields.
- Re-indexes remaining planned items to close the gap (1..N).
- `mission.total_locations` unchanged (skip ≠ delete).

**Responses:** `200` → `{"message": "Location skipped successfully", "location_id": 7}`. · `404` → `Mission not found` / `Location not found`. · `409` → active. · `422` → missing `location_id`.

---

## 5. Business Logic Specs

### 5.1 `app/utils/geo.py`

```python
import math

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters (WGS-84 approx)."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing in degrees 0..360 (0 = north, clockwise)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360
```

Round results to 2 decimals when persisting.

### 5.2 Nearest-Neighbor

```python
def nearest_neighbor(points: list[Point], start_idx: int) -> list[Point]:
    """Greedy order: always move to closest unvisited point."""
```

- Precompute full distance matrix (n ≤ 200 → 40k cells, fine).
- Start at `start_idx`; repeatedly pick nearest unvisited; break ties by lower index.
- O(n²).

### 5.3 2-opt refinement

```python
def two_opt(order: list[Point], dist_matrix: list[list[float]]) -> list[Point]:
    """Reverse segments whenever it shortens the tour. One or more passes until no improvement."""
```

- For each pair `(i, j)`, compute delta from reversing segment `i..j`; apply if negative.
- Loop until no improvement (max passes bounded, e.g. 100) — O(n²) per pass, acceptable for n ≤ 200.
- First point (start) stays fixed as tour is a path, not a cycle (we do **not** return to start).

### 5.4 Service orchestration

```python
def plan(self, mission_id: int) -> RouteResponse:
    mission = _get_mission_or_404(mission_id)
    _ensure_inactive(mission)                       # 409
    locs = location_repo.get_all_by_mission(mission_id)
    if not locs:
        raise HTTPException(422, "Mission has no locations to plan")
    start_idx = index of mission.start_location_id if set else 0
    order = nearest_neighbor([(lat, lon, id)...], start_idx)
    order = two_opt(order, dist_matrix)
    location_repo.update_sequence_batch(mission_id, [ids in order])
    _write_distances_and_bearings(mission_id, order)   # per consecutive pair
    mission.status = MissionStatus.READY
    mission.total_locations = len(locs)
    db.commit()
    return build_route(mission_id)
```

### 5.5 Distances & bearings write

For each consecutive pair in planned order, `haversine`/`bearing` between them; store on the **later** row. First row keeps `NULL`. Skipped/unplanned rows keep `NULL`.

### 5.6 Reorder validation pseudocode

```python
def reorder(self, mission_id: int, payload: list[ReorderItem]) -> RouteResponse:
    mission = _get_mission_or_404(mission_id)
    _ensure_inactive(mission)
    if not payload:
        raise HTTPException(422, "Reorder list cannot be empty")
    existing = {loc.id for loc in location_repo.get_all_by_mission(mission_id)}
    submitted = {it.location_id for it in payload}
    if submitted != existing:
        missing = existing - submitted
        raise HTTPException(422, f"Reorder list must include all mission locations. Missing: {sorted(missing)}")
    orders = [it.sequence_order for it in payload]
    if len(orders) != len(set(orders)):
        raise HTTPException(422, "Duplicate sequence_order values are not allowed")
    ordered_ids = [it.location_id for it in sorted(payload, key=lambda x: x.sequence_order)]
    location_repo.update_sequence_batch(mission_id, ordered_ids)
    _write_distances_and_bearings(mission_id, ordered_ids)
    mission.status = MissionStatus.READY
    db.commit()
    return build_route(mission_id)
```

### 5.7 Error message catalog (English)

| Condition | Status | Message |
|-----------|--------|---------|
| Mission not found | 404 | `Mission not found` |
| Location not found | 404 | `Location not found` |
| Active mission | 409 | `Cannot plan while mission is <status>` |
| No locations | 422 | `Mission has no locations to plan` |
| Empty reorder list | 422 | `Reorder list cannot be empty` |
| Foreign location in reorder | 422 | `location_id <id> does not belong to this mission` |
| Incomplete reorder | 422 | `Reorder list must include all mission locations. Missing: [...]` |
| Duplicate order | 422 | `Duplicate sequence_order values are not allowed` |
| Skip missing id | 422 | `location_id is required` |

---

## 6. Acceptance Criteria

### 6.1 Unit tests

| # | Test | Expectation |
|---|------|-------------|
| U01 | `haversine` known pair | e.g. Monas→Thamrin ≈ 1.2 km ± 1%; same point = 0 |
| U02 | `bearing` directions | N=0, E=90, S=180, W=270 (approx) |
| U03 | `nearest_neighbor` 3 points | Starts at start point; returns shortest-first order |
| U04 | `nearest_neighbor` single point | Returns `[start]` |
| U05 | `two_opt` on crossed path | Path total distance ≤ NN-only total |
| U06 | `two_opt` no-op on optimal | Order unchanged |
| U07 | `plan` empty mission | 422 `Mission has no locations to plan` |
| U08 | `plan` single location | sequence=1, dist/bearing NULL, status READY |
| U09 | `plan` writes fields | sequence_order 1..N unique; distance/bearing populated on rows 2..N |
| U10 | `plan` on RUNNING | 409 |
| U11 | `reorder` full valid list | Order matches submitted; status PENDING reset; READY |
| U12 | `reorder` incomplete list | 422 with missing ids |
| U13 | `reorder` duplicate sequence_order | 422 |
| U14 | `reorder` foreign location | 422 |
| U15 | `skip` location | status SKIPPED, sequence NULL, gap re-indexed |
| U16 | `build_route` total_distance | Sum of planned distances correct |

### 6.2 End-to-end / integration tests

| # | Test | Expectation |
|---|------|-------------|
| E01 | Create mission + upload 5 towers + plan | 200; 5 items; sequence 1..5; route GET matches |
| E02 | GET route before planning | Items listed with `sequence_order=null`; total_distance 0 |
| E03 | Plan twice | Second plan overwrites order (deterministic for same data) |
| E04 | Reorder then GET route | Manual order persists |
| E05 | Reorder then Plan | Auto-plan replaces manual order |
| E06 | Skip mid-route | Status SKIPPED; remaining sequence re-indexed; plan returns same 200 |
| E07 | Plan on RUNNING mission | 409 |
| E08 | Plan on mission with 0 locations | 422 |
| E09 | Route of deleted mission | 404 |
| E10 | Full `pytest` suite | All existing tests still pass (no regressions) |

### 6.3 Verification commands

```bash
cd ~/Cellular-Discovery-Service/backend

# Create + upload + plan
curl -s -X POST http://localhost:8000/api/v1/missions/ -H "Content-Type: application/json" \
  -d '{"name":"Planner Smoke"}'
printf 'cellular_tower_id,cellular_tower_name,latitude,longitude\nT1,A,-6.200,106.800\nT2,B,-6.260,106.820\nT3,C,-6.150,106.780\nT4,D,-6.220,106.860\nT5,E,-6.280,106.830\n' > /tmp/t5.csv
curl -s -X POST http://localhost:8000/api/v1/missions/1/locations/upload -F "file=@/tmp/t5.csv"

curl -s -X POST http://localhost:8000/api/v1/missions/1/plan
curl -s http://localhost:8000/api/v1/missions/1/route

# Reorder (IDs depend on your rows)
curl -s -X POST http://localhost:8000/api/v1/missions/1/route/reorder \
  -H "Content-Type: application/json" \
  -d '[{"location_id":3,"sequence_order":1},{"location_id":1,"sequence_order":2},{"location_id":4,"sequence_order":3},{"location_id":2,"sequence_order":4},{"location_id":5,"sequence_order":5}]'

# Skip
curl -s -X POST http://localhost:8000/api/v1/missions/1/route/skip \
  -H "Content-Type: application/json" -d '{"location_id":5}'

# Geo sanity check
.venv/bin/python -c "from app.utils.geo import haversine, bearing; \
print(haversine(-6.2088,106.8456,-6.2615,106.8106)); print(bearing(-6.2088,106.8456,-6.2615,106.8106))"

# Full suite
.venv/bin/pytest -q
```

---

### Checklist

- [ ] `geo.py` haversine + bearing (stdlib only)
- [ ] NN + 2-opt implemented and unit-tested
- [ ] `update_sequence_batch`, `clear_sequence_order`, `mark_skipped` repository methods
- [ ] Plan/reorder/skip/route endpoints
- [ ] Status transition `IDLE/PLANNING/READY/STOPPED/FAILED → READY`
- [ ] Reorder validation (complete set, unique order, ownership)
- [ ] Distance/bearing + total_distance computation
- [ ] All Acceptance Criteria (U01–U16, E01–E10) pass
