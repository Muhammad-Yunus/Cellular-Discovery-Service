# FEATURE_IMPROVEMENT_05_SCANNER_INTEGRATION.md

> Mission Planner Epic — Phase 5: Scanner Integration (link scan_sessions to mission_locations)

| Field | Value |
|-------|-------|
| **Epic** | Mission Planner (Improvement_Epic/) |
| **Phase** | 5 of 10 |
| **Dependencies** | [03_MISSION_CRUD](FEATURE_IMPROVEMENT_03_MISSION_CRUD.md), [04_PLANNER_ALGORITHM](FEATURE_IMPROVEMENT_04_PLANNER_ALGORITHM.md) |
| **Estimated LOC** | ~120 |
| **Complexity** | Low |
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

- Extend the existing scan pipeline so a scan session can record **which mission location it belongs to**, without breaking the manual `/scan` flow.
- Store the link on `scan_sessions.mission_location_id` (nullable column from Phase 1).
- Expose `mission_location_id` in `ScanSessionResponse`.
- **Zero behavior change** for existing callers: parameter is keyword-only with `None` default.

---

## 2. Backend Tasks

1. [ ] Modify `ScanSessionRepository.create` (`backend/app/repositories/scan_session_repository.py`) to accept optional `mission_location_id` and persist it.
2. [ ] Modify `ScanService.execute_scan` (`backend/app/services/scan_service.py`) to accept keyword-only `mission_location_id: int | None = None` and pass it through to the repository.
3. [ ] Add optional `mission_location_id` field to `ScanSessionResponse` (`backend/app/schemas/scan.py`).
4. [ ] Update `ScanService._to_response` to populate the new field.
5. [ ] Verify the existing `/api/v1/scan` router call site needs **no changes** (it omits the new param).
6. [ ] Run full test suite (no regressions).

---

## 3. File Changes

### Modified files
| Path | Description |
|------|-------------|
| `backend/app/repositories/scan_session_repository.py` | `create(..., mission_location_id: Optional[int] = None)` |
| `backend/app/services/scan_service.py` | `execute_scan(..., *, mission_location_id=None)` + `_to_response` |
| `backend/app/schemas/scan.py` | `ScanSessionResponse.mission_location_id: Optional[int] = None` |
| `backend/tests/` | New/extended tests (see Acceptance Criteria) |

No new files. No router changes.

---

## 4. API Specs

### Existing endpoint — unchanged signature

`POST /api/v1/scan` — no new request fields.

**Response now includes:**
```json
{
  "id": 456,
  "scan_time": "2026-07-31T09:00:00Z",
  "tty_port": "/dev/ttyUSB0",
  "latitude": -6.2088,
  "longitude": 106.8456,
  "mission_location_id": null,
  "created_at": "2026-07-31T09:00:00Z",
  "results": [ ... ]
}
```

`mission_location_id` is `null` for all manual scans (backward compatible). It becomes non-null only when the executor (Phase 6) triggers a mission scan.

### New service method signature (used by Phase 6 executor)

```python
def execute_scan(
    self,
    port: str,
    timeout: int = 30,
    *,
    mission_location_id: int | None = None,
) -> ScanSessionResponse:
```

- Keyword-only → any existing positional calls are unaffected.
- `None` default → no link recorded.

---

## 5. Business Logic Specs

### 5.1 Repository change

```python
def create(
    self,
    tty_port: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    mission_location_id: Optional[int] = None,
) -> ScanSession:
    session = ScanSession(
        tty_port=tty_port,
        latitude=latitude,
        longitude=longitude,
        mission_location_id=mission_location_id,
    )
    self.db.add(session)
    self.db.commit()
    self.db.refresh(session)
    return session
```

### 5.2 Service change

```python
def execute_scan(self, port: str, timeout: int = 30, *, mission_location_id: int | None = None) -> ScanSessionResponse:
    location = self.gps_provider.get_location()
    cli_response = self.cli_adapter.execute(port=port, timeout=timeout)
    session = self.session_repo.create(
        tty_port=port,
        latitude=location.latitude,
        longitude=location.longitude,
        mission_location_id=mission_location_id,
    )
    ...
```

### 5.3 Schema change

```python
class ScanSessionResponse(BaseModel):
    id: int
    scan_time: datetime
    tty_port: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    mission_location_id: Optional[int] = None
    created_at: datetime
    results: list[ScanResultResponse] = []
```

`_to_response` passes `mission_location_id=session.mission_location_id`.

### 5.4 Integrity notes

- If `mission_location_id` is provided and the mission_locations row does not exist → FK violation → `IntegrityError`. The executor (Phase 6) always passes a valid id it just read, so this is a defensive concern only; wrap executor calls in try/except (Phase 6).
- The reverse link (`mission_locations.scan_session_id`) is written by the executor after the scan succeeds (Phase 6). Phase 5 only stores the session → location direction.

### 5.5 No-op checklist (backward compatibility)

- `POST /api/v1/scan` still works identically.
- `ScanResultFlatResponse` untouched in this phase (flat list enrichment is Phase 8 mission-scoped queries).
- No DB migration needed (column already added in Phase 1).

---

## 6. Acceptance Criteria

### 6.1 Unit tests

| # | Test | Expectation |
|---|------|-------------|
| U01 | `ScanSessionRepository.create` without mission_location_id | Session persisted with `mission_location_id=None` |
| U02 | `ScanSessionRepository.create` with mission_location_id | Value persisted |
| U03 | `ScanService.execute_scan` without kwarg | Returns response with `mission_location_id=None`; GPS + CLI still called (mocked) |
| U04 | `ScanService.execute_scan` with `mission_location_id=5` | Response `mission_location_id == 5`; stored on session row |
| U05 | `ScanSessionResponse` model | Field present, optional, defaults None |
| U06 | Existing `ScanSessionResponse` construction sites | Compile clean (no required-field breakage) |

### 6.2 End-to-end / integration tests

| # | Test | Expectation |
|---|------|-------------|
| E01 | `POST /api/v1/scan` (real/CLI mocked) | 200; body has `mission_location_id: null` |
| E02 | Service-level scan with mission ref (session commit) | DB row `scan_sessions.mission_location_id` matches |
| E03 | Full `pytest` suite | All existing tests still pass (no regressions) |

### 6.3 Verification commands

```bash
cd ~/Cellular-Discovery-Service/backend

# Existing scan still works (CLI mock not needed if hardware available; otherwise unit test path):
.venv/bin/pytest -q tests/test_services.py tests/test_api.py tests/test_database.py

# Manual sanity: create a location row for mission 1, then simulate executor-style call:
.venv/bin/python - <<'PY'
from app.db.database import get_db
from app.repositories.scan_session_repository import ScanSessionRepository
db = next(get_db())
s = ScanSessionRepository(db).create(
    tty_port="/dev/ttyUSB0", latitude=-6.20, longitude=106.84, mission_location_id=1,
)
print("mission_location_id stored:", s.mission_location_id)
db.close()
PY

# Full suite
.venv/bin/pytest -q
```

---

### Checklist

- [ ] `ScanSessionRepository.create` accepts `mission_location_id`
- [ ] `ScanService.execute_scan` keyword-only param added
- [ ] `ScanSessionResponse.mission_location_id` exposed
- [ ] `_to_response` populates the field
- [ ] `/api/v1/scan` call site unchanged
- [ ] All Acceptance Criteria (U01–U06, E01–E03) pass
