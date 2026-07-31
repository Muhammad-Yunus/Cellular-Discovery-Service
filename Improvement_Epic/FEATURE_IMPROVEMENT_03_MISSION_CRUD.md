# FEATURE_IMPROVEMENT_03_MISSION_CRUD.md

> Mission Planner Epic — Phase 3: Mission CRUD (Header Management)

| Field | Value |
|-------|-------|
| **Epic** | Mission Planner (Improvement_Epic/) |
| **Phase** | 3 of 10 |
| **Dependencies** | [02_LOCATION_MANAGEMENT](FEATURE_IMPROVEMENT_02_LOCATION_MANAGEMENT.md) |
| **Estimated LOC** | ~450 |
| **Complexity** | Medium |
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

- Provide full CRUD for the `missions` header under `/api/v1/missions/`.
- Status field is **read-only via CRUD** — transitions are owned by later phases (plan → `PLANNING`/`READY`, executor → `STARTING`/`RUNNING`/etc.). CRUD only creates (`IDLE`) and guards deletes.
- Guard mutation/delete while the mission is active (`RUNNING`, `STARTING`, `PAUSED`).
- Validate `start_location_id` belongs to **this mission** (per-mission locations model).
- Expose nested `locations` on the detail endpoint, ordered by `sequence_order`.
- English error messages, repo `Repository` + `Service` + `Router` pattern (matches Phase 2).

---

## 2. Backend Tasks

1. [ ] Create Pydantic schemas in `app/schemas/mission.py` (incl. `MissionStatus` enum matching DB CHECK).
2. [ ] Create `MissionRepository` in `app/repositories/mission_repository.py`.
3. [ ] Create `MissionService` in `app/services/mission_service.py` (guards + validations).
4. [ ] Create router `app/api/routers/missions.py`.
5. [ ] Register router in `app/main.py` (prefix `/api/v1/missions`).
6. [ ] Reuse `MissionLocationRepository` from Phase 2 for nested `locations` in detail + location-belonging checks.
7. [ ] Default `radius_meters` from `settings.MISSION_DEFAULT_RADIUS_METERS` (Phase 10 config; fallback constant 20 until then).
8. [ ] Write unit + integration tests.
9. [ ] Run full test suite (no regressions).

---

## 3. File Changes

### New files
| Path | Description |
|------|-------------|
| `backend/app/schemas/mission.py` | `MissionStatus`, `MissionCreate`, `MissionUpdate`, `MissionResponse`, `MissionDetailResponse`, `MissionListResponse`, `MissionDeleteResponse` |
| `backend/app/repositories/mission_repository.py` | DB access: create, get, list, update, delete |
| `backend/app/services/mission_service.py` | Guards, validations, counter/nested-location assembly |
| `backend/app/api/routers/missions.py` | `/api/v1/missions/*` endpoints |

### Modified files
| Path | Description |
|------|-------------|
| `backend/app/main.py` | Import + include `missions` router |
| `backend/app/schemas/__init__.py` | Export new schemas |
| `backend/app/services/__init__.py` | Export `MissionService` |
| `backend/tests/test_api.py` (or new `tests/test_missions.py`) | New endpoint tests |

> **Route note:** `missions.py` uses prefix `/api/v1/missions`; the Phase-2 router uses `/api/v1/missions/{mission_id}/locations`. No conflicts (distinct path shapes). Include both.

---

## 4. API Specs

### 4.1 `POST /api/v1/missions/`

Create a mission draft. Status always starts `IDLE`; `total_locations` starts `0`.

**Request body:**
```json
{
  "name": "Jakarta Utara Sweep",
  "description": "Scan during drone testing",
  "radius_meters": 20,
  "tty_port": null
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | str | **yes** | stripped; non-empty |
| `description` | str \| null | no | |
| `radius_meters` | int | no | default `settings.MISSION_DEFAULT_RADIUS_METERS` (20); must be `> 0` |
| `tty_port` | str \| null | no | override for `DEFAULT_TTY`; null → fallback |

> `start_location_id` is **not accepted at create** — a mission has no locations yet (locations are per-mission and created after the mission exists). Set it later via PATCH.

**Responses:**
`201 Created` → `MissionResponse` (see 4.3). · `422` → missing `name` / `radius_meters <= 0`.

### 4.2 `GET /api/v1/missions/`

Paginated list.

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `page` | int | 1 | `ge=1` |
| `page_size` | int | 10 | `ge=1`, `le=100` |
| `status` | str \| null | — | exact match against `MissionStatus`; invalid value → 422 |
| `search` | str \| null | — | ILIKE on `name` |

**Response:**
```json
{
  "items": [
    {
      "id": 3,
      "name": "Jakarta Utara Sweep",
      "description": "Scan during drone testing",
      "status": "IDLE",
      "radius_meters": 20,
      "tty_port": null,
      "start_location_id": null,
      "current_location_id": null,
      "total_locations": 0,
      "visited_locations": 0,
      "progress_percent": 0.0,
      "started_at": null,
      "completed_at": null,
      "stopped_at": null,
      "created_at": "2026-07-31T09:00:00Z",
      "updated_at": "2026-07-31T09:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

Default sort: `-created_at`. Invalid `status` → 422 `Invalid mission status: <value>`.

### 4.3 `GET /api/v1/missions/{mission_id}`

Detail incl. nested `locations` (Phase 2 response shape), ordered by `sequence_order` then `id`.

**Response:** `MissionDetailResponse` = `MissionResponse` + `"locations": [MissionLocationResponse]`.

`404` → `Mission not found`.

### 4.4 `PATCH /api/v1/missions/{mission_id}`

Update editable fields. **Status cannot be changed via PATCH.**

**Request body (all optional):**
```json
{
  "name": "Jakarta Utara Sweep v2",
  "description": "Updated notes",
  "radius_meters": 30,
  "tty_port": "/dev/ttyUSB1",
  "start_location_id": 5
}
```

| Field | Notes |
|-------|-------|
| `name` | stripped; non-empty if provided |
| `description` | set to `null` to clear |
| `radius_meters` | must be `> 0` |
| `tty_port` | set to `null` to clear (fall back to `DEFAULT_TTY`) |
| `start_location_id` | must reference a `mission_locations` row of **this mission**; `null` clears |

**Guards:**
- Mission status in `{RUNNING, STARTING, PAUSED}` → `409 Conflict: Cannot update mission while it is <status>`.
- `start_location_id` not belonging to this mission → `422: start_location_id does not belong to this mission`.
- Changing `name`/`description` **does not invalidate the plan**; changing `start_location_id`, `radius_meters`, or `tty_port` sets `sequence_order` to `NULL` for all locations (needs re-plan; see Phase 4).

**Responses:** `200` → `MissionResponse`. · `404` → `Mission not found`. · `409`/`422` per guards.

### 4.5 `DELETE /api/v1/missions/{mission_id}`

**Allowed statuses:** `IDLE`, `PLANNING`, `READY`, `STOPPED`, `COMPLETED`, `FAILED`.

**Blocked statuses:** `STARTING`, `RUNNING`, `PAUSED` → `409 Conflict: Cannot delete mission while it is <status>`.

**Cascade:** deletes all `mission_locations` rows (FK `ON DELETE CASCADE`). `scan_sessions` linked via `mission_locations.scan_session_id` are **kept** (FK `ON DELETE SET NULL`).

**Response:**
```json
{"message": "Mission deleted successfully", "id": 3}
```

`404` → `Mission not found`.

---

## 5. Business Logic Specs

### 5.1 `MissionStatus` enum

```python
class MissionStatus(str, Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    READY = "READY"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
```

Must mirror the DB CHECK constraint exactly (Phase 1, 5.1).

### 5.2 `MissionRepository` methods

| Method | Signature | Returns |
|--------|-----------|---------|
| `create` | `(name, description, radius_meters, tty_port)` | `Mission` |
| `get_by_id` | `(mission_id)` | `Mission \| None` |
| `list` | `(page, page_size, status, search)` | `(missions, total)` |
| `update` | `(mission, fields: dict)` | `Mission` |
| `delete` | `(mission)` | `bool` |

Pattern matches `ScanResultRepository`: `__init__(self, db: Session)`, explicit `commit()` + `refresh()` in mutators.

### 5.3 `MissionService` logic

```python
def create(self, payload: MissionCreate) -> Mission:
    mission = repo.create(
        name=payload.name.strip(),
        description=payload.description,
        radius_meters=payload.radius_meters or settings.MISSION_DEFAULT_RADIUS_METERS,
        tty_port=payload.tty_port,
    )
    return mission

def get_detail(self, mission_id: int) -> MissionDetailResponse | None:
    mission = repo.get_by_id(mission_id)
    if not mission:
        return None
    locations, _ = location_repo.list_by_mission(mission_id, page=1, page_size=1_000_000, search=None)
    return build_detail(mission, locations)

def update(self, mission_id: int, payload: MissionUpdate) -> Mission | None:
    mission = repo.get_by_id(mission_id) or raise 404
    _ensure_inactive(mission)               # 409 guard
    if payload.start_location_id is not None:
        _ensure_location_belongs(mission.id, payload.start_location_id)   # 422
    structural = any(k in {"radius_meters", "tty_port", "start_location_id"} for k in payload.model_fields_set)
    mission = repo.update(mission, payload.model_dump(exclude_unset=True, exclude_none=True))
    if structural:
        location_repo.clear_sequence_order(mission_id)   # invalidate plan
    return mission

def delete(self, mission_id: int) -> bool:
    mission = repo.get_by_id(mission_id) or raise 404
    _ensure_inactive(mission)               # 409 guard
    return repo.delete(mission)
```

### 5.4 Guard helpers

```python
ACTIVE_STATUSES = {"STARTING", "RUNNING", "PAUSED"}

def _ensure_inactive(mission: Mission) -> None:
    if mission.status in ACTIVE_STATUSES:
        raise HTTPException(409, f"Cannot update mission while it is {mission.status}")

def _ensure_location_belongs(mission_id: int, location_id: int) -> None:
    if not location_repo.get_by_id(mission_id, location_id):
        raise HTTPException(422, "start_location_id does not belong to this mission")
```

### 5.5 `progress_percent`

Computed field (not stored): `round(visited_locations / total_locations * 100, 1)` when `total_locations > 0`, else `0.0`.

### 5.6 Error message catalog (English)

| Condition | Status | Message |
|-----------|--------|---------|
| Mission not found | 404 | `Mission not found` |
| Active mission update/delete | 409 | `Cannot update mission while it is <status>` / `Cannot delete mission while it is <status>` |
| start_location_id foreign mission | 422 | `start_location_id does not belong to this mission` |
| Invalid status filter | 422 | `Invalid mission status: <value>` |
| Invalid radius | 422 | `radius_meters must be greater than 0` (Pydantic `gt=0`) |
| Empty name | 422 | `Mission name is required` |

---

## 6. Acceptance Criteria

### 6.1 Unit tests

| # | Test | Expectation |
|---|------|-------------|
| U01 | `repo.create` | Returns Mission with `status=IDLE`, `total_locations=0`, default radius |
| U02 | create without name | 422 `Mission name is required` |
| U03 | create with `radius_meters=0` | 422 (`gt=0`) |
| U04 | `repo.list` status filter | Only matching statuses returned |
| U05 | `repo.list` search | ILIKE on name, case-insensitive |
| U06 | `service.get_detail` | Nested `locations` ordered by `sequence_order`; `progress_percent` correct (e.g. 3/10 → 30.0) |
| U07 | `service.update` field patch | name/description/radius/tty updated; status unchanged |
| U08 | `service.update` clear tty/start | `tty_port` and `start_location_id` become NULL |
| U09 | `service.update` foreign start_location | 422 `start_location_id does not belong to this mission` |
| U10 | `service.update` on RUNNING | 409 |
| U11 | `service.update` structural field | `sequence_order` cleared (plan invalidated) |
| U12 | `service.delete` on RUNNING/PAUSED/STARTING | 409 |
| U13 | `service.delete` on IDLE/STOPPED/COMPLETED | Succeeds; cascade removes locations |
| U14 | `MissionStatus` values | Match DB CHECK list exactly |

### 6.2 End-to-end / integration tests

| # | Test | Expectation |
|---|------|-------------|
| E01 | POST create → GET list | Mission appears with IDLE, total 0 |
| E02 | Upload CSV (Phase 2) → GET detail | `total_locations` synced; nested `locations` present |
| E03 | PATCH start_location_id to a valid own location | 200; field set |
| E04 | PATCH start_location_id to other mission's location | 422 |
| E05 | PATCH on RUNNING mission | 409 |
| E06 | DELETE mission with locations | 200; `missions` row gone; `mission_locations` gone; linked `scan_sessions` still exist |
| E07 | DELETE on RUNNING mission | 409 |
| E08 | GET missing mission | 404 `Mission not found` |
| E09 | List with invalid status | 422 `Invalid mission status: <value>` |
| E10 | Full `pytest` suite | All existing tests still pass (no regressions) |

### 6.3 Verification commands

```bash
cd ~/Cellular-Discovery-Service/backend

# 1. Create
curl -s -X POST http://localhost:8000/api/v1/missions/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Smoke Mission","description":"test","radius_meters":20}'

# 2. List
curl -s "http://localhost:8000/api/v1/missions/?status=IDLE"

# 3. Upload locations then get detail
printf 'cellular_tower_id,cellular_tower_name,latitude,longitude\nTWR-001,A,-6.20,106.84\nTWR-002,B,-6.26,106.81\n' > /tmp/towers.csv
curl -s -X POST http://localhost:8000/api/v1/missions/1/locations/upload -F "file=@/tmp/towers.csv"
curl -s http://localhost:8000/api/v1/missions/1

# 4. Patch
curl -s -X PATCH http://localhost:8000/api/v1/missions/1 \
  -H "Content-Type: application/json" -d '{"start_location_id":1,"radius_meters":30}'

# 5. Delete
curl -s -X DELETE http://localhost:8000/api/v1/missions/1

# 6. Full suite
.venv/bin/pytest -q
```

---

### Checklist

- [ ] `MissionStatus` enum mirrors DB CHECK
- [ ] Schemas + repository + service + router created
- [ ] Router registered in `app/main.py`
- [ ] Nested `locations` in detail endpoint
- [ ] `start_location_id` ownership validation
- [ ] Active-mission mutation/delete guards (409)
- [ ] Plan invalidation on structural PATCH
- [ ] `progress_percent` computed field
- [ ] All Acceptance Criteria (U01–U14, E01–E10) pass
