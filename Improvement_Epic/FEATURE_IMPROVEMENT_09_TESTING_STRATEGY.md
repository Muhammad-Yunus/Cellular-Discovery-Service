# FEATURE_IMPROVEMENT_09_TESTING_STRATEGY.md

> Mission Planner Epic — Phase 9: Testing Strategy (fixtures, unit + integration matrix, coverage)

| Field | Value |
|-------|-------|
| **Epic** | Mission Planner (Improvement_Epic/) |
| **Phase** | 9 of 10 |
| **Dependencies** | Phases 01–08 (all features must exist) |
| **Estimated LOC** | ~700 (test code) |
| **Complexity** | Medium |
| **Status** | Draft |
| **Target** | Dev backend at `~/Cellular-Discovery-Service/backend` |

---

## 📑 Table of Contents

1. [Goals](#1-goals)
2. [Backend Tasks](#2-backend-tasks)
3. [File Changes](#3-file-changes)
4. [Test Environment & Fixtures](#4-test-environment--fixtures)
5. [Test Matrix](#5-test-matrix)
6. [Acceptance Criteria](#6-acceptance-criteria)

---

## 1. Goals

- Consolidate all Acceptance Criteria from Phases 01–08 into one executable test strategy.
- Reuse the existing sqlite-based `conftest.py` pattern (schema-stripped `Base.metadata.create_all`); no DB server needed for unit/integration tests.
- Add deterministic fakes: sequence-aware mock GPS and a configurable fake CLI adapter.
- Verify the **full mission lifecycle** end-to-end (create → upload → plan → start → visits → complete) plus the failure paths and concurrency rule.
- Target **>80% statement coverage** on all new mission modules.
- Prove zero regressions: full existing suite must stay green.

---

## 2. Backend Tasks

1. [ ] Extend `tests/conftest.py` with mission fixtures (fake GPS, fake CLI, mission-with-plan factory).
2. [ ] Add `tests/test_geo.py` — pure function tests (Phase 4 U01–U02).
3. [ ] Add `tests/test_locations.py` — Phase 2 U01–U12.
4. [ ] Add `tests/test_missions.py` — Phase 3 U01–U14.
5. [ ] Add `tests/test_planning.py` — Phase 4 U03–U16.
6. [ ] Add `tests/test_executor.py` — Phase 6 U01–U14 + E01–E07 (asyncio/TestClient).
7. [ ] Add `tests/test_ws_mission.py` — Phase 7 U01–U08 + E01–E06.
8. [ ] Add `tests/test_mission_scans.py` — Phase 8 U01–U09 + E01–E06.
9. [ ] Extend `tests/test_database.py` — Phase 1 U01–U10 (model/FK/CHECK/relationship).
10. [ ] Run `coverage` over the new modules; fix gaps to reach 80%+.
11. [ ] Run full suite; verify all existing tests still pass.

---

## 3. File Changes

### New files
| Path | Description |
|------|-------------|
| `backend/tests/test_geo.py` | haversine / bearing |
| `backend/tests/test_locations.py` | CSV parse, UPSERT, list, delete, guards |
| `backend/tests/test_missions.py` | mission CRUD + guards + plan invalidation |
| `backend/tests/test_planning.py` | NN, 2-opt, plan/reorder/skip/route |
| `backend/tests/test_executor.py` | singleton, lifecycle, GPS/scan failures, restore |
| `backend/tests/test_ws_mission.py` | mission WS events |
| `backend/tests/test_mission_scans.py` | mission-scoped list + export |

### Modified files
| Path | Description |
|------|-------------|
| `backend/tests/conftest.py` | New fixtures (below) |
| `backend/tests/test_database.py` | Phase 1 model/constraint tests |

---

## 4. Test Environment & Fixtures

### 4.1 DB strategy (unchanged baseline)

- `tests/conftest.py` uses `sqlite:///./test.db` (file-based), `PRAGMA foreign_keys=ON`, `_strip_schemas()` removes `schema="app"`, `create_all`/`drop_all` per test function.
- Implications for new models:
  - `missions` ↔ `mission_locations` circular FKs — handled by SQLAlchemy table ordering at `create_all`.
  - SQLite enforces `UNIQUE`, `CHECK`, `CASCADE`, `SET NULL` (with PRAGMA on) → all Phase-1 constraint tests runnable locally.
  - Alembic migration tests (Phase 1 E01–E04) run **outside** the sqlite fixture against the dev Postgres (`alembic upgrade/downgrade`), never inside unit tests.

### 4.2 New fixtures

```python
@pytest.fixture
def fake_gps_provider():
    """Sequence-controlled GPS. Supports fail_n (raises GPSError N times) and waypoints()."""
    class FakeGPS:
        def __init__(self, waypoints=None, fail_n=0):
            self.waypoints = list(waypoints or [(-6.20, 106.80)])
            self._i = 0
            self._fail_remaining = fail_n
        def get_location(self):
            if self._fail_remaining > 0:
                self._fail_remaining -= 1
                raise GPSError("simulated gps loss")
            w = self.waypoints[self._i % len(self.waypoints)]
            self._i += 1
            return GpsLocation(latitude=w[0], longitude=w[1])
    return FakeGPS


@pytest.fixture
def fake_cli_adapter():
    """Returns canned scan results; raises if `fail_next` set; records calls."""
    class FakeCLI:
        def __init__(self, results=None):
            self.results = results or [ScanResultItem(operator_name="Telkomsel", mcc="510", mnc="10", rat="LTE", status="OK")]
            self.calls = []
            self.fail_next = False
        def execute(self, port, timeout):
            self.calls.append({"port": port, "timeout": timeout})
            if self.fail_next:
                self.fail_next = False
                raise CLIError("simulated cli failure")
            return CLIResponse(results=self.results)
    return FakeCLI


@pytest.fixture
def mission_factory(db_session, client):
    """Helper: creates mission + uploads towers + optionally plans.
       Returns callable(mission_kwargs, towers: list[dict], plan: bool) -> mission_id."""
    def _make(mission_kwargs=None, towers=None, plan=True):
        # POST /api/v1/missions -> id
        # POST /api/v1/missions/{id}/locations/upload (CSV string via multipart)
        # optionally POST /api/v1/missions/{id}/plan
        return mission_id
    return _make


@pytest.fixture
def executor(fake_gps_provider, fake_cli_adapter):
    """MissionExecutor wired with fakes; requires asyncio runner (pytest-asyncio or anyio)."""
    return MissionExecutor(gps_provider=fake_gps_provider, scan_service_factory=lambda db: fake_scan_service)
```

Notes:
- For the executor's `asyncio` tests, use `pytest.mark.anyio` or `pytest-asyncio` — pick the plugin already available in `.venv`; if none, run via `asyncio.run()` inside sync tests.
- Executor must be given a `scan_service_factory` that returns a real `ScanService` with the **fake CLI adapter** + fake GPS so Phase-5 integration (session + mission_location_id link) is exercised.

### 4.3 Sample mission topology for lifecycle tests

Use 3 towers with coordinates that the fake GPS visits in order (e.g. same-ish coordinates so geofence always hits, radius 20):

```csv
cellular_tower_id,cellular_tower_name,latitude,longitude
T1,A,-6.20000,106.80000
T2,B,-6.20001,106.80001
T3,C,-6.20002,106.80002
```

GPS waypoints = the 3 tower coords → each poll falls inside the 20 m radius → deterministic `mission_visit` × 3 → `COMPLETED`.

---

## 5. Test Matrix

### 5.1 Unit tests (consolidated from Phase docs)

| Module | Count | Source |
|--------|-------|--------|
| `test_geo.py` | 2 | P4 U01–U02 |
| `test_locations.py` | 12 | P2 U01–U12 |
| `test_missions.py` | 14 | P3 U01–U14 |
| `test_planning.py` | 14 | P4 U03–U16 |
| `test_executor.py` | 14 | P6 U01–U14 |
| `test_ws_mission.py` | 8 | P7 U01–U08 |
| `test_mission_scans.py` | 9 | P8 U01–U09 |
| `test_database.py` (+new) | 10 | P1 U01–U10 |

**Priority edge cases (must not be skipped):**
- DB: `UNIQUE (mission_id, cellular_tower_id)`, 1-to-1 `scan_session_id`, CHECK status/coords, cascade vs set-null, circular FK (P1).
- Concurrency: second `start` → 409 (P6 U02); delete/location-modify while RUNNING → 409 (P2, P3).
- Failures: scan error non-fatal skip (P6 U07); GPS threshold → FAILED (P6 U08).
- Planner: 2-opt never worse than NN (P4 U05); reorder full-set + duplicate + ownership validation (P4 U11–U14).

### 5.2 Integration tests

| # | Scenario | Steps | Expectation |
|---|----------|-------|-------------|
| I01 | Full lifecycle (E2E) | `mission_factory(plan=True)` → `start` → poll `/status` until COMPLETED | COMPLETED; `visited_locations==3`; 3 sessions linked via `mission_location_id`; `/scans` returns them |
| I02 | Concurrent start | Fire 2 `start` for different missions (same event loop) | One 200, one 409 `Another mission is already running` |
| I03 | Pause/resume/stop over HTTP | start → pause → resume → stop | Status sequence RUNNING→PAUSED→RUNNING→STOPPED; `/logs` reflects |
| I04 | Restart recovery | Set mission RUNNING in DB directly → call executor `startup()` | Status STOPPED, `stopped_at` set |
| I05 | WS live updates | Connect `/ws/mission`, run I01 | Receives started → progress → visit×3 → completed in order |
| I06 | GPS failure path | fake GPS `fail_n=threshold` → start | Mission FAILED; `mission_failed` event |
| I07 | Mission scans export | After I01, `GET /scans/export` | CSV with 3 rows + tower columns |
| I08 | No-regression sweep | `pytest -q` (full suite) | All green |

### 5.3 Coverage target

```bash
coverage run -m pytest -q
coverage report -m --include="app/core/mission_executor.py,app/services/mission_*,app/services/location_service.py,app/api/routers/mission_*.py,app/utils/geo.py,app/repositories/mission_*"
```

Target: **≥80%** statement coverage per listed module. Report gaps → add tests, not assertions.

---

## 6. Acceptance Criteria

| # | Test | Expectation |
|---|------|-------------|
| U01 | All Phase-1 model/constraint tests pass | sqlite enforces FK/CHECK/UNIQUE as specified |
| U02 | All Phase-2 location tests pass | CSV parse/UPSERT/guards covered |
| U03 | All Phase-3 mission tests pass | CRUD + guards + plan invalidation covered |
| U04 | All Phase-4 planner tests pass | NN/2-opt/reorder/skip covered |
| U05 | All Phase-6 executor tests pass | lifecycle + concurrency + failures covered |
| U06 | All Phase-7 WS tests pass | event payloads + channel isolation covered |
| U07 | All Phase-8 scans tests pass | scoped list/export covered |
| U08 | Integration I01–I07 pass | Full mission flow verified end-to-end |
| U09 | Coverage report | ≥80% on all new modules |
| U10 | Full existing suite | 100% green (no regressions) |

### 6.1 Verification commands

```bash
cd ~/Cellular-Discovery-Service/backend

# New tests only
.venv/bin/pytest -q tests/test_geo.py tests/test_locations.py tests/test_missions.py \
  tests/test_planning.py tests/test_executor.py tests/test_ws_mission.py tests/test_mission_scans.py

# Coverage on new modules
.venv/bin/coverage run -m pytest -q
.venv/bin/coverage report -m --include="app/core/mission_executor.py,app/services/mission_*.py,app/services/location_service.py,app/api/routers/mission_*.py,app/utils/geo.py,app/repositories/mission_*.py"

# Migration smoke (dev DB only, optional in this phase)
.venv/bin/alembic upgrade head && .venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head

# Full sweep
.venv/bin/pytest -q
```

---

### Checklist

- [ ] conftest fixtures: fake GPS (waypoints + fail_n), fake CLI, mission_factory, executor
- [ ] 7 new test modules + `test_database.py` extension
- [ ] Integration I01–I08 green
- [ ] Coverage ≥80% on new modules
- [ ] Full suite green (no regressions)
- [ ] Migration round-trip verified against dev DB
