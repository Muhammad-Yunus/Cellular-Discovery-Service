# FEATURE_IMPROVEMENT_08_MISSION_SCOPED_QUERIES.md

> Mission Planner Epic — Phase 8: Mission-Scoped Scan History (list + CSV export)

| Field | Value |
|-------|-------|
| **Epic** | Mission Planner (epic/) |
| **Phase** | 8 of 10 |
| **Dependencies** | [05_SCANNER_INTEGRATION](FEATURE_IMPROVEMENT_05_SCANNER_INTEGRATION.md), [06_BACKGROUND_EXECUTOR](FEATURE_IMPROVEMENT_06_BACKGROUND_EXECUTOR.md) |
| **Estimated LOC** | ~220 |
| **Complexity** | Low-Medium |
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

- Expose the scan history **belonging to a mission**:
  - `GET /api/v1/missions/{mission_id}/scans` — paginated flat list (reuses `ScanResultFlatResponse` + `PaginatedResponse`).
  - `GET /api/v1/missions/{mission_id}/scans/export` — CSV scoped to the mission.
- Filter path: `scan_results` → `scan_sessions` → rows whose session id appears in `mission_locations.scan_session_id` for the mission.
- Reuse the same filters as the global scans list (`search`, `rat`, `start_time`, `end_time`, `sort`) with identical validation.
- Enrich items with the owning `mission_location_id` (+ tower id/name) so the FE Scans tab can link each scan back to a tower.
- No changes to the global `/api/v1/scans` endpoints.

---

## 2. Backend Tasks

1. [ ] Add optional `mission_location_id` to `ScanResultFlatResponse` (`app/schemas/scan.py`) — default `None`, backward compatible.
2. [ ] Add `get_mission_flat` to `ScanResultRepository` (`app/repositories/scan_result_repository.py`) — mission-scoped flat query with all filters.
3. [ ] Create `MissionScanService` (`app/services/mission_scan_service.py`) — list + CSV assembly, filter validation (mirrors `HistoryService`).
4. [ ] Create router `app/api/routers/mission_scans.py` — `/api/v1/missions/{mission_id}/scans` and `/scans/export`.
5. [ ] Register router in `app/main.py`.
6. [ ] Write unit + integration tests.
7. [ ] Run full test suite (no regressions).

---

## 3. File Changes

### New files
| Path | Description |
|------|-------------|
| `backend/app/services/mission_scan_service.py` | `get_mission_scans`, `get_mission_csv` |
| `backend/app/api/routers/mission_scans.py` | Mission-scoped list + export endpoints |

### Modified files
| Path | Description |
|------|-------------|
| `backend/app/repositories/scan_result_repository.py` | `get_mission_flat(mission_id, ...)` |
| `backend/app/schemas/scan.py` | `ScanResultFlatResponse.mission_location_id: Optional[int] = None` |
| `backend/app/main.py` | Include `mission_scans` router |
| `backend/app/services/__init__.py` | Export `MissionScanService` |
| `backend/tests/` | `tests/test_mission_scans.py` |

---

## 4. API Specs

### 4.1 `GET /api/v1/missions/{mission_id}/scans`

Flat, paginated scan results for the mission (each row = one `scan_result`).

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `page` | int | 1 | `ge=1` |
| `page_size` | int | 10 | `ge=1`, `le=100` |
| `search` | str \| null | — | ILIKE on tty_port / operator_name / mcc / mnc |
| `sort` | str | `-scan_time` | `scan_time` or `-scan_time` |
| `rat` | str \| null | — | GSM/LTE/UMTS/ALL (case-insensitive, same validation as global) |
| `start_time` | datetime \| null | — | `scan_time >= start_time`; `start_time <= end_time` enforced |
| `end_time` | datetime \| null | — | `scan_time <= end_time` |

**Response** (`PaginatedResponse`):
```json
{
  "items": [
    {
      "id": 123,
      "scan_session_id": 456,
      "scan_time": "2026-07-31T09:00:00Z",
      "tty_port": "/dev/ttyUSB0",
      "latitude": -6.2088,
      "longitude": 106.8456,
      "mission_location_id": 45,
      "created_at": "2026-07-31T09:00:00Z",
      "operator_name": "Telkomsel",
      "mcc": "510",
      "mnc": "10",
      "rat": "LTE",
      "status": "OK"
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 10,
  "total_pages": 1
}
```

`404` → `Mission not found` · `422` → invalid `rat` / time range (same messages as global history).

> Empty result set is a valid `200` (mission exists but has no linked scans yet).

### 4.2 `GET /api/v1/missions/{mission_id}/scans/export`

CSV scoped to the mission; same filters as 4.1 (no pagination).

**Response headers:** `Content-Type: text/csv`, `Content-Disposition: attachment; filename="mission_<id>_scans.csv"`.

**Columns** (global CSV + tower link):
```
id, session_id, scan_time, tty_port, latitude, longitude, created_at,
operator_name, mcc, mnc, rat, status,
mission_location_id, cellular_tower_id, cellular_tower_name
```

`404` → `Mission not found`.

---

## 5. Business Logic Specs

### 5.1 Repository `get_mission_flat`

```python
def get_mission_flat(
    self,
    mission_id: int,
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    sort: str = "-scan_time",
    rat: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> tuple[list[ScanResult], int]:
    """Scan results whose session is linked to a mission location."""
    query = (
        self.db.query(ScanResult)
        .join(ScanResult.session)
        .join(ScanSession.mission_location)          # relationship from Phase 1
        .filter(MissionLocation.mission_id == mission_id)
    )
    # ... identical filter chain as get_all_flat (search/rat/time) ...
    # ... same ordering + offset/limit ...
    return results, total
```

- `ScanSession.mission_location` relationship (Phase 1, 5.6) provides the join; only sessions with `scan_session_id` set on a location of this mission appear.
- Ordering: default `desc(ScanSession.scan_time)` when `sort` starts with `-`, else `asc`.

### 5.2 Service

```python
class MissionScanService:
    def __init__(self, db: Session):
        self.db = db
        self.result_repo = ScanResultRepository(db)

    def get_mission_scans(self, mission_id, page, page_size, search, sort, rat, start_time, end_time) -> PaginatedResponse:
        # validate time range + rat (copy HistoryService rules)
        results, total = self.result_repo.get_mission_flat(...)
        return PaginatedResponse(items=[_to_flat(r) for r in results], total=..., page=..., page_size=..., total_pages=...)

    def get_mission_csv(self, mission_id, search, sort, rat, start_time, end_time) -> str:
        results, _ = self.result_repo.get_mission_flat(page=1, page_size=999999, ...)
        # csv.StringIO writer, columns from §4.2
        return output.getvalue()

    def _mission_exists(self, mission_id) -> bool:
        # used by router to 404 before returning empty list
```

`_to_flat(r)` maps a `ScanResult` to `ScanResultFlatResponse`, including:
```python
mission_location_id=r.session.mission_location_id if r.session else None,
```
and (for export only) tower id/name via `r.session.mission_location.cellular_tower_id/name`.

### 5.3 Filter validation (identical to global)

- `start_time > end_time` → `422 start_time cannot be greater than end_time`.
- `rat` outside `{GSM, LTE, UMTS, ALL}` → `422 Only GSM, LTE, UMTS, or ALL is allowed for the rat parameter`.
- `ALL` → treated as no filter (mirrors `HistoryService`).

### 5.4 Error message catalog (English)

| Condition | Status | Message |
|-----------|--------|---------|
| Mission not found | 404 | `Mission not found` |
| Bad time range | 422 | `start_time cannot be greater than end_time` |
| Bad rat | 422 | `Only GSM, LTE, UMTS, or ALL is allowed for the rat parameter` |

---

## 6. Acceptance Criteria

### 6.1 Unit tests

| # | Test | Expectation |
|---|------|-------------|
| U01 | `get_mission_flat` returns only linked sessions | Scans of other missions / manual scans excluded |
| U02 | `get_mission_flat` search filter | ILIKE across tty_port/operator/mcc/mnc |
| U03 | `get_mission_flat` rat filter | Only matching rat rows; ALL = no filter |
| U04 | `get_mission_flat` time range | Respects start/end; start>end raises ValueError |
| U05 | `get_mission_flat` pagination | Correct slice + total |
| U06 | `_to_flat` mission_location_id | Populated from session; None for manual scans |
| U07 | `get_mission_csv` header | Exact column list incl. mission_location_id, cellular_tower_id, cellular_tower_name |
| U08 | `get_mission_scans` empty mission | 200 with empty items, total 0 |
| U09 | `ScanResultFlatResponse` new field | Optional, default None — global list untouched |

### 6.2 End-to-end / integration tests

| # | Test | Expectation |
|---|------|-------------|
| E01 | Mission with 2 visited towers + 1 manual scan | `/missions/{id}/scans` returns only the 2 mission scans |
| E02 | GET scans with `rat=LTE` | Only LTE rows |
| E03 | GET scans/export | CSV downloadable; rows match list; contains tower columns |
| E04 | GET scans of missing mission | 404 `Mission not found` |
| E05 | Global `/api/v1/scans` unaffected | Still returns all scans incl. manual |
| E06 | Full `pytest` suite | All existing tests still pass (no regressions) |

### 6.3 Verification commands

```bash
cd ~/Cellular-Discovery-Service/backend

# List mission scans
curl -s "http://localhost:8000/api/v1/missions/1/scans?page=1&page_size=10"

# With filters
curl -s "http://localhost:8000/api/v1/missions/1/scans?rat=LTE"

# Export
curl -s -OJ "http://localhost:8000/api/v1/missions/1/scans/export"

# Full suite
.venv/bin/pytest -q
```

---

### Checklist

- [ ] `ScanResultFlatResponse.mission_location_id` added (optional)
- [ ] `get_mission_flat` with all filters
- [ ] `MissionScanService` list + CSV
- [ ] Router registered in `app/main.py`
- [ ] Export filename `mission_<id>_scans.csv`
- [ ] Global scans endpoints unchanged
- [ ] All Acceptance Criteria (U01–U09, E01–E06) pass
