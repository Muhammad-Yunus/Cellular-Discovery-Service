# FEATURE_IMPROVEMENT_02_LOCATION_MANAGEMENT.md

> Mission Planner Epic — Phase 2: Location Management (Tower CSV Import & CRUD)

| Field | Value |
|-------|-------|
| **Epic** | Mission Planner (epic/) |
| **Phase** | 2 of 10 |
| **Dependencies** | [FEATURE_IMPROVEMENT_01_DATABASE_SCHEMA](FEATURE_IMPROVEMENT_01_DATABASE_SCHEMA.md) |
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

- Provide full CRUD for `mission_locations` (per-mission tower data) under `/api/v1/missions/{mission_id}/locations/`.
- Implement **CSV upload** with row-level validation, batch tracking, and **UPSERT** semantics (`UNIQUE (mission_id, cellular_tower_id)`).
- Expose paginated list with search, single detail, single delete, and bulk-delete-by-batch.
- Guard destructive operations (upload/delete/bulk-delete) while a mission is active (`STARTING`/`RUNNING`/`PAUSED`).
- Keep all error messages in **English** (repo convention, e.g. history router).
- Follow existing repo patterns: `Repository` + `Service` + `Router`, Pydantic schemas, `get_db` dependency.

---

## 2. Backend Tasks

1. [ ] Create `MissionLocation` ORM model (done in Phase 1) — reuse it.
2. [ ] Create Pydantic schemas in `app/schemas/mission_location.py`.
3. [ ] Create `MissionLocationRepository` in `app/repositories/mission_location_repository.py`.
4. [ ] Create `LocationService` in `app/services/location_service.py` (CSV parse, validation, UPSERT).
5. [ ] Create router `app/api/routers/mission_locations.py`.
6. [ ] Register router in `app/main.py` with prefix `/api/v1/missions`.
7. [ ] Add `csv` parsing helper (stdlib `csv` module — no new dependency).
8. [ ] Sync `missions.total_locations` after upload / bulk-delete.
9. [ ] Write unit + integration tests.
10. [ ] Run full test suite (no regressions).

---

## 3. File Changes

### New files
| Path | Description |
|------|-------------|
| `backend/app/schemas/mission_location.py` | Pydantic request/response models for locations |
| `backend/app/repositories/mission_location_repository.py` | DB access: UPSERT, list, get, delete, bulk-delete |
| `backend/app/services/location_service.py` | CSV parsing, validation, batch orchestration |
| `backend/app/api/routers/mission_locations.py` | `/api/v1/missions/{mission_id}/locations/*` endpoints |

### Modified files
| Path | Description |
|------|-------------|
| `backend/app/main.py` | Import + include `mission_locations` router |
| `backend/app/schemas/__init__.py` | Export new schemas (match existing style) |
| `backend/app/services/__init__.py` | Export `LocationService` (match existing style) |
| `backend/tests/test_api.py` (or new `tests/test_locations.py`) | New endpoint tests |

---

## 4. API Specs

All routes under `/api/v1/missions/{mission_id}/locations`.

### 4.1 `POST /api/v1/missions/{mission_id}/locations/upload`

Multipart/form-data upload of tower CSV for a mission.

**Request:** `file` (required) — CSV file.

**CSV format (header row mandatory):**
```
cellular_tower_id,cellular_tower_name,latitude,longitude
TWR-001,Jakarta Pusat,-6.2088,106.8456
TWR-002,Jakarta Selatan,-6.2615,106.8106
```

**Validation rules:**
- Header must contain `cellular_tower_id`, `latitude`, `longitude` (name optional column but recommended).
- `latitude` must parse as float and be within `[-90, 90]`.
- `longitude` must parse as float and be within `[-180, 180]`.
- `cellular_tower_id` non-empty; leading/trailing whitespace stripped.
- Rows with errors are collected; valid rows still processed.
- Duplicate `cellular_tower_id` **within the file or DB** → UPSERT (update name/coords).
- Max rows per file: 10 000 (configurable via `MISSION_MAX_LOCATIONS`). Exceeding → 422.
- Empty file / no valid rows → 422 with message `CSV file is empty or has no valid rows`.

**Guard:** if mission status is `STARTING`, `RUNNING`, or `PAUSED` → `409 Conflict: Cannot modify locations while mission is running`.

**Responses:**

`200 OK`
```json
{
  "upload_batch_id": "e5c7f2a4-b8d9-4e3f-a1b2-c3d4e5f6a7b8",
  "mission_id": 3,
  "total_rows": 50,
  "inserted": 47,
  "updated": 2,
  "skipped": 1,
  "errors": [
    {"row": 7, "error": "Invalid latitude: abc"},
    {"row": 12, "error": "Longitude out of range: 200.5"}
  ]
}
```

`404` → `Mission not found` · `422` → validation message · `409` → running guard.

### 4.2 `GET /api/v1/missions/{mission_id}/locations`

Paginated list.

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `page` | int | 1 | `ge=1` |
| `page_size` | int | 10 | `ge=1`, `le=100` |
| `search` | str | — | ILIKE on `cellular_tower_id` or `cellular_tower_name` |

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "mission_id": 3,
      "cellular_tower_id": "TWR-001",
      "cellular_tower_name": "Jakarta Pusat",
      "latitude": -6.2088,
      "longitude": 106.8456,
      "upload_batch_id": "e5c7f2a4-...",
      "sequence_order": null,
      "status": "PENDING",
      "distance_from_previous_meters": null,
      "bearing_from_previous_degrees": null,
      "actual_visit_time": null,
      "visited_at": null,
      "created_at": "2026-07-31T09:00:00Z",
      "updated_at": "2026-07-31T09:00:00Z"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 10
}
```

`404` → `Mission not found`.

### 4.3 `GET /api/v1/missions/{mission_id}/locations/{location_id}`

**Response:** single `MissionLocationResponse` (same shape as list item).

`404` → `Mission not found` or `Location not found`.

### 4.4 `DELETE /api/v1/missions/{mission_id}/locations/{location_id}`

**Guard:** if mission status is `STARTING`/`RUNNING`/`PAUSED` → `409 Conflict: Cannot modify locations while mission is running`.

**Response:**
```json
{"message": "Location deleted successfully", "id": 42}
```

`404` → `Mission not found` / `Location not found`.

> Note: `missions.start_location_id`/`current_location_id` reference this row via `ON DELETE SET NULL` — deleting the current target location auto-clears those fields.

### 4.5 `POST /api/v1/missions/{mission_id}/locations/bulk-delete`

Body: `{"upload_batch_id": "e5c7f2a4-..."}` — deletes all rows of that batch for this mission.

**Guard:** same 409 as single delete.

**Response:**
```json
{"message": "Deleted 23 locations from batch e5c7f2a4-...", "deleted": 23}
```

`404` → `Mission not found` · `422` → missing/invalid `upload_batch_id`.

---

## 5. Business Logic Specs

### 5.1 CSV parsing (`LocationService._parse_csv`)

```python
def parse_csv(raw: bytes) -> list[dict]:
    """Return list of row dicts: {row_number, cellular_tower_id, cellular_tower_name, latitude, longitude, errors}"""
```

- Decode as UTF-8; `csv.DictReader`.
- First row must include `cellular_tower_id`, `latitude`, `longitude` headers → else raise `ValueError("Invalid CSV header, expected cellular_tower_id,cellular_tower_name,latitude,longitude")`.
- Row-level error collection (never abort whole file for one bad row).
- Strip whitespace on all string cells.

### 5.2 UPSERT (`MissionLocationRepository.upsert_batch`)

```python
def upsert_batch(self, mission_id: int, rows: list[dict], batch_id: str) -> tuple[int, int]:
    """Return (inserted, updated). Uses SELECT existing cellular_tower_ids for the mission,
    then insert-new / update-existing. One commit at the end."""
```

- Match on `(mission_id, cellular_tower_id)`.
- Update sets `cellular_tower_name`, `latitude`, `longitude`, `updated_at`.
- Every row (new + updated) gets `upload_batch_id = batch_id`.

### 5.3 Batch id

- `uuid4().hex` (36-char) generated once per upload call.

### 5.4 Total counters sync

After upload or bulk-delete, call:

```python
mission.total_locations = repo.count_by_mission(mission_id)
```

This keeps `missions.total_locations` in sync without a trigger. (Counter used by executor/phase 06.)

### 5.5 Status guard helper

```python
def _ensure_mutable(mission: Mission) -> None:
    if mission.status in ("STARTING", "RUNNING", "PAUSED"):
        raise HTTPException(409, "Cannot modify locations while mission is running")
```

Applied in `upload`, `delete`, `bulk-delete`.

### 5.6 Repository methods summary

| Method | Signature | Returns |
|--------|-----------|---------|
| `upsert_batch` | `(mission_id, rows, batch_id)` | `(inserted, updated)` |
| `list_by_mission` | `(mission_id, page, page_size, search)` | `(locations, total)` |
| `get_by_id` | `(mission_id, location_id)` | `MissionLocation \| None` |
| `delete_by_id` | `(mission_id, location_id)` | `bool` |
| `bulk_delete_by_batch` | `(mission_id, upload_batch_id)` | `int` (deleted count) |
| `count_by_mission` | `(mission_id)` | `int` |

Follow the existing repository pattern: `__init__(self, db: Session)`, `self.db` field, explicit `commit()` at the end of mutating methods (match `ScanResultRepository`).

### 5.7 Error message catalog (English)

| Condition | Status | Message |
|-----------|--------|---------|
| Mission not found | 404 | `Mission not found` |
| Location not found | 404 | `Location not found` |
| Mission STARTING/RUNNING/PAUSED | 409 | `Cannot modify locations while mission is running` |
| Bad header | 422 | `Invalid CSV header, expected cellular_tower_id,cellular_tower_name,latitude,longitude` |
| No valid rows | 422 | `CSV file is empty or has no valid rows` |
| Too many rows | 422 | `CSV file exceeds maximum of {limit} rows` |
| Missing file | 422 | `No file uploaded` |

---

## 6. Acceptance Criteria

### 6.1 Unit tests

| # | Test | Expectation |
|---|------|-------------|
| U01 | `parse_csv` valid file | Correct dicts; 3 rows parsed; no errors |
| U02 | `parse_csv` missing header | Raises `ValueError` with header message |
| U03 | `parse_csv` bad lat row | Row flagged with error `Invalid latitude: <value>`; other rows fine |
| U04 | `parse_csv` out-of-range lon | Row flagged `Longitude out of range: <value>` |
| U05 | `parse_csv` empty file | Service raises 422 `CSV file is empty or has no valid rows` |
| U06 | `upsert_batch` new rows | `inserted == N`, `updated == 0` |
| U07 | `upsert_batch` existing ids | `inserted == 0`, `updated == N`; name/coords overwritten |
| U08 | `upsert_batch` mixed | Correct split; all rows share batch id |
| U09 | `list_by_mission` pagination | Correct page slice + total |
| U10 | `list_by_mission` search | ILIKE matches tower_id and name case-insensitively |
| U11 | `count_by_mission` after upsert | Matches rows inserted |
| U12 | `_ensure_mutable` on RUNNING/PAUSED | Raises HTTPException 409 |

### 6.2 End-to-end / integration tests

| # | Test | Expectation |
|---|------|-------------|
| E01 | POST upload valid CSV (mission IDLE) | 200; `total_rows/inserted` match; `upload_batch_id` present |
| E02 | POST upload same CSV twice | Second call: `updated == total_rows`, `inserted == 0` |
| E03 | GET list after upload | Items + `total` correct; ordering by id |
| E04 | GET list `search=TWR-0` | Only matching tower_ids/names returned |
| E05 | GET single location | Full `MissionLocationResponse` shape |
| E06 | DELETE single location | Row gone; `GET` returns 404; `total_locations` decremented |
| E07 | DELETE on RUNNING/PAUSED mission | 409; row still present |
| E08 | POST bulk-delete by batch | `deleted == batch count`; rows gone |
| E09 | Upload to non-existent mission | 404 `Mission not found` |
| E10 | Upload bad-header CSV | 422 with header message |
| E11 | Upload while mission RUNNING/PAUSED | 409; no rows inserted |
| E12 | Full `pytest` suite | All existing tests still pass (no regressions) |

### 6.3 Verification commands

```bash
cd ~/Cellular-Discovery-Service/backend

# 1. Create a test mission (needs Phase 1 tables + minimal mission creation — or via raw SQL)
.venv/bin/python -c "from app.db.database import engine; from sqlalchemy import text; \
engine.connect().execute(text(\"INSERT INTO app.missions (name,status) VALUES ('smoke-test','IDLE') RETURNING id\"))"

# 2. Upload a CSV
printf 'cellular_tower_id,cellular_tower_name,latitude,longitude\nTWR-001,Jakarta Pusat,-6.2088,106.8456\nTWR-002,Jakarta Selatan,-6.2615,106.8106\n' > /tmp/towers.csv
curl -s -X POST http://localhost:8000/api/v1/missions/1/locations/upload \
  -F "file=@/tmp/towers.csv"

# 3. List
curl -s "http://localhost:8000/api/v1/missions/1/locations?search=TWR"

# 4. Detail + delete
curl -s http://localhost:8000/api/v1/missions/1/locations/1
curl -s -X DELETE http://localhost:8000/api/v1/missions/1/locations/1

# 5. Bulk delete
curl -s -X POST http://localhost:8000/api/v1/missions/1/locations/bulk-delete \
  -H "Content-Type: application/json" -d '{"upload_batch_id":"<batch_id>"}'

# 6. Full suite
.venv/bin/pytest -q
```

---

### Checklist

- [ ] Schemas + repository + service + router created
- [ ] Router registered in `app/main.py`
- [ ] CSV parse with row-level errors
- [ ] UPSERT semantics verified (insert + update)
- [ ] `total_locations` counter sync
- [ ] Active-mission guard (409: STARTING/RUNNING/PAUSED)
- [ ] English error messages everywhere
- [ ] All Acceptance Criteria (U01–U12, E01–E12) pass
