# FEATURE_IMPROVEMENT_06_BACKGROUND_EXECUTOR.md

> Mission Planner Epic — Phase 6: Background Executor (Mission Runner + Control Endpoints)

| Field | Value |
|-------|-------|
| **Epic** | Mission Planner (epic/) |
| **Phase** | 6 of 10 |
| **Dependencies** | [03_MISSION_CRUD](FEATURE_IMPROVEMENT_03_MISSION_CRUD.md), [04_PLANNER_ALGORITHM](FEATURE_IMPROVEMENT_04_PLANNER_ALGORITHM.md), [05_SCANNER_INTEGRATION](FEATURE_IMPROVEMENT_05_SCANNER_INTEGRATION.md) |
| **Estimated LOC** | ~650 |
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

- Run missions in the background with a **singleton `MissionExecutor`** — at most **one** mission `RUNNING` at any time.
- Poll GPS, detect geofence entry (within `radius_meters` of the next pending location), auto-trigger a scan, and advance the mission.
- Own all state transitions: `STARTING → RUNNING → (PAUSED ⇄ RUNNING) → COMPLETED | STOPPED | FAILED`.
- On app startup, any leftover mission from a previous process with status `STARTING`, `RUNNING`, or `PAUSED` is restored to `STOPPED`.
- Provide control + introspection endpoints: `start`, `pause`, `resume`, `stop`, `status`, `logs`.
- Non-fatal failures (single scan error) log & continue; fatal failures (GPS lost N×, critical DB error) → `FAILED`.
- Reuse existing `ScanService` (Phase 5) and existing GPS providers (`app/gps/factory.py`).

---

## 2. Backend Tasks

1. [ ] Create `backend/app/core/mission_executor.py` — singleton `MissionExecutor`.
2. [ ] Add `backend/app/api/routers/mission_control.py` — control endpoints.
3. [ ] Wire executor into `app/main.py` lifespan (`app.state.mission_executor`, startup restore, shutdown cancel).
4. [ ] Add dependency provider `get_mission_executor` in `app/api/dependencies/providers.py`.
5. [ ] Add in-memory per-mission log ring buffer (`collections.deque`, `maxlen=MISSION_LOG_SIZE`).
6. [ ] Add settings keys (Phase 10 defines defaults, reference them now): `MISSION_POLL_INTERVAL`, `MISSION_GPS_FAILURE_THRESHOLD`, `MISSION_CLI_TIMEOUT`, `MISSION_START_GPS_TIMEOUT`, `MISSION_LOG_SIZE`.
7. [ ] Emit WebSocket `mission` events on transitions (Phase 7 builds the WS channel; executor calls `ws_manager.broadcast` — safe if no subscribers).
8. [ ] Write unit + integration tests (mock GPS + fake CLI adapter).
9. [ ] Run full test suite (no regressions).

---

## 3. File Changes

### New files
| Path | Description |
|------|-------------|
| `backend/app/core/mission_executor.py` | `MissionExecutor` singleton (loop, lock, tasks, logs) |
| `backend/app/api/routers/mission_control.py` | `/api/v1/missions/{id}/start\|pause\|resume\|stop\|status\|logs` |

### Modified files
| Path | Description |
|------|-------------|
| `backend/app/main.py` | lifespan: instantiate executor, `startup()`, `shutdown()`; include control router |
| `backend/app/api/dependencies/providers.py` | `get_mission_executor` dependency |
| `backend/app/config/settings.py` | Mission settings fields |
| `backend/app/repositories/mission_repository.py` | Add `get_running_count`, `set_status` helpers |
| `backend/app/repositories/mission_location_repository.py` | Add `get_next_pending`, `mark_visited`, `set_scan_session` |
| `backend/tests/` | `tests/test_executor.py` (+ fixtures for fake GPS/CLI) |

---

## 4. API Specs

All under `/api/v1/missions/{mission_id}`.

### 4.1 `POST /api/v1/missions/{mission_id}/start`

**Allowed status:** `IDLE`, `READY` (must have a plan — `sequence_order` not null on ≥1 location).

**Guards:**
- Another mission already `RUNNING` (DB or in-memory task) → `409 Conflict: Another mission is already running`.
- This mission already has an active task → `409 Conflict: Mission is already running`.
- No plan → `422: Mission has no planned locations. Run plan first`.

**Behavior:** status → `STARTING` (persisted). GPS availability checked within `MISSION_START_GPS_TIMEOUT` (default 5s). On success → `RUNNING`, `started_at=now`, spawn background task. On GPS timeout → `FAILED` (`failed reason` in log), return `503 Service Unavailable: GPS not available`.

**Response:** `200` → `{"message": "Mission started", "mission_id": 3, "status": "RUNNING"}`.

### 4.2 `POST /api/v1/missions/{mission_id}/pause`

**Allowed:** `RUNNING` → `PAUSED`. Task stays alive (holds singleton lock), loop sleeps.

**Responses:** `200` → `{"message":"Mission paused","status":"PAUSED"}`. · `409` → if not RUNNING: `Cannot pause mission while it is <status>`.

### 4.3 `POST /api/v1/missions/{mission_id}/resume`

**Allowed:** `PAUSED` → `RUNNING`.

`200` → `{"message":"Mission resumed","status":"RUNNING"}` · `409` → if not PAUSED.

### 4.4 `POST /api/v1/missions/{mission_id}/stop`

**Allowed:** `STARTING`, `RUNNING`, `PAUSED` → `STOPPED`. Cancels the background task if alive; `stopped_at=now`.

`200` → `{"message":"Mission stopped","status":"STOPPED"}` · `409` → if `IDLE`/`READY`/terminal: `Cannot stop mission while it is <status>`.

### 4.5 `GET /api/v1/missions/{mission_id}/status`

**Response:**
```json
{
  "mission_id": 3,
  "name": "Jakarta Utara Sweep",
  "status": "RUNNING",
  "started_at": "2026-07-31T09:00:00Z",
  "completed_at": null,
  "stopped_at": null,
  "total_locations": 10,
  "visited_locations": 3,
  "progress_percent": 30.0,
  "current_location_id": 45,
  "active": true,
  "gps_failure_count": 0,
  "last_error": null
}
```

`active` reflects whether an executor task exists for this mission. `gps_failure_count`/`last_error` are executor runtime state (not persisted).

### 4.6 `GET /api/v1/missions/{mission_id}/logs`

**Response:** JSON array, newest last, ring-buffered:
```json
[
  {"timestamp": "2026-07-31T09:00:01Z", "event_type": "STARTING", "message": "Mission 3 starting"},
  {"timestamp": "2026-07-31T09:00:06Z", "event_type": "RUNNING", "message": "GPS OK, target TWR-005 at 14.2m"},
  {"timestamp": "2026-07-31T09:01:12Z", "event_type": "VISITED", "message": "TWR-005 scanned, session 456 linked"}
]
```

`event_type` ∈ {`STARTING`,`RUNNING`,`PAUSED`,`RESUMED`,`VISITED`,`SKIPPED`,`STOPPED`,`COMPLETED`,`FAILED`,`GPS_ERROR`,`SCAN_ERROR`,`INFO`}.

---

## 5. Business Logic Specs

### 5.1 `MissionExecutor` skeleton

```python
class MissionExecutor:
    def __init__(self, gps_provider: GPSProvider, scan_service_factory=None):
        self.active_tasks: dict[int, asyncio.Task] = {}
        self.lock = asyncio.Lock()
        self.gps_provider = gps_provider
        self.logs: dict[int, deque] = defaultdict(lambda: deque(maxlen=settings.MISSION_LOG_SIZE))
        self._shutdown = False
        self._scan_factory = scan_service_factory  # for DI in tests

    async def startup(self) -> None:
        """Restore missions left in STARTING/RUNNING/PAUSED to STOPPED (app restart recovery)."""
        db = SessionLocal()
        try:
            rows = db.query(Mission).filter(Mission.status.in_(["STARTING", "RUNNING", "PAUSED"])).all()
            for m in rows:
                m.status = "STOPPED"
                m.stopped_at = datetime.now(timezone.utc)
                self._log(m.id, "STOPPED", "Mission restored to STOPPED on app startup")
            db.commit()
        finally:
            db.close()

    async def shutdown(self) -> None:
        self._shutdown = True
        for mission_id, task in list(self.active_tasks.items()):
            task.cancel()
        await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
        self.active_tasks.clear()
```

### 5.2 `start` (singleton discipline)

```python
async def start(self, mission_id: int) -> dict:
    if self.lock.locked():
        raise HTTPException(409, "Another mission is already running")

    db = SessionLocal()
    try:
        if _count_running(db) > 0:
            raise HTTPException(409, "Another mission is already running")
        mission = db.query(Mission).get(mission_id) or raise 404
        if mission_id in self.active_tasks:
            raise HTTPException(409, "Mission is already running")
        if mission.status not in {"IDLE", "READY"}:
            raise HTTPException(409, f"Cannot start mission while it is {mission.status}")
        if not _has_planned_locations(db, mission_id):
            raise HTTPException(422, "Mission has no planned locations. Run plan first")

        mission.status = "STARTING"
        mission.started_at = None
        db.commit()

        # GPS availability check (non-fatal startup gate)
        try:
            await self._gps_ok(timeout=settings.MISSION_START_GPS_TIMEOUT)
        except GPSError:
            mission.status = "FAILED"
            db.commit()
            raise HTTPException(503, "GPS not available")

        mission.status = "RUNNING"
        mission.started_at = datetime.now(timezone.utc)
        db.commit()
        self._log(mission_id, "STARTING", f"Mission {mission_id} starting")
    finally:
        db.close()

    self.active_tasks[mission_id] = asyncio.create_task(self._run(mission_id))
    return {"message": "Mission started", "mission_id": mission_id, "status": "RUNNING"}
```

### 5.3 `_run` main loop (holds lock for the whole mission)

```python
async def _run(self, mission_id: int) -> None:
    async with self.lock:
        try:
            while not self._shutdown:
                mission = _get_mission(mission_id)
                if mission is None:
                    break
                if mission.status == "PAUSED":
                    self._log(mission_id, "PAUSED", "Mission paused")
                    await asyncio.sleep(settings.MISSION_POLL_INTERVAL)
                    continue
                if mission.status != "RUNNING":
                    break

                location = await asyncio.to_thread(self._gps_read)   # blocking serial → threadpool
                if location is None:
                    self._gps_failure(mission_id)                    # increments; FAILED at threshold
                    await asyncio.sleep(settings.MISSION_POLL_INTERVAL)
                    continue
                self._gps_failure_reset()

                target = _get_next_pending(mission_id)               # PENDING, min sequence_order
                if target is None:
                    mission.status = "COMPLETED"
                    mission.completed_at = datetime.now(timezone.utc)
                    db.commit()
                    self._log(mission_id, "COMPLETED", "All locations visited")
                    await self._broadcast("mission_completed", mission_id)
                    break

                dist = haversine(location.latitude, location.longitude,
                                 target.latitude, target.longitude)
                await self._broadcast("mission_progress", mission_id,
                                      {"distance_to_target_meters": round(dist, 2)})

                if dist <= (mission.radius_meters or 20):
                    await self._visit(mission, target, location, dist)
                else:
                    self._log(mission_id, "INFO", f"Target {target.cellular_tower_id} at {round(dist,1)}m")

                await asyncio.sleep(settings.MISSION_POLL_INTERVAL)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            mission = _get_mission(mission_id)
            if mission and mission.status == "RUNNING":
                mission.status = "FAILED"
                db.commit()
                self._log(mission_id, "FAILED", f"Fatal error: {e}")
                await self._broadcast("mission_failed", mission_id, {"reason": str(e)})
        finally:
            self.active_tasks.pop(mission_id, None)
```

### 5.4 `_visit` — geofence hit → scan

```python
async def _visit(self, mission, target, location, dist) -> None:
    port = mission.tty_port or settings.DEFAULT_TTY
    if mission.tty_port is None:
        logger.warning(f"Mission {mission.id} falling back to DEFAULT_TTY={port}")
        self._log(mission.id, "INFO", f"No tty_port override, using DEFAULT_TTY={port}")

    scan = await asyncio.to_thread(
        self._run_scan, port=port, lat=location.latitude, lon=location.longitude,
        timeout=settings.MISSION_CLI_TIMEOUT, mission_location_id=target.id,
    )   # ScanService.execute_scan(..., *, mission_location_id=target.id) from Phase 5

    target.status = "VISITED"
    target.scan_session_id = scan.id
    target.actual_visit_time = datetime.now(timezone.utc)
    target.visited_at = target.actual_visit_time
    mission.visited_locations += 1
    mission.current_location_id = target.id
    db.commit()
    self._log(mission.id, "VISITED", f"{target.cellular_tower_id} scanned, session {scan.id} linked")
    await self._broadcast("mission_visit", mission.id,
                          {"location_id": target.id, "scan_session_id": scan.id, "distance_m": round(dist, 2)})
```

**Non-fatal scan error:** wrap `_run_scan` in try/except → log `SCAN_ERROR`, mark target `SKIPPED` (or keep PENDING? — spec: **skip** and continue, do not fail the mission), continue loop.

### 5.5 GPS failure handling

- `gps_failure_count` in executor memory; reset on success.
- Each consecutive failure logs `GPS_ERROR`; when count ≥ `MISSION_GPS_FAILURE_THRESHOLD` (default 10) → status `FAILED`, broadcast `mission_failed`, break loop.
- `_gps_read` calls `self.gps_provider.get_location()` inside `asyncio.to_thread` (serial reads block); returns None on `GPSError`.

### 5.6 Control methods

```python
async def pause(self, mission_id):   # RUNNING -> PAUSED (persist + log)
async def resume(self, mission_id):  # PAUSED -> RUNNING (persist + log)
async def stop(self, mission_id):
    # status in (STARTING, RUNNING, PAUSED) -> STOPPED, stopped_at=now, cancel task if alive
```

`stop` cancels the task → the loop's `CancelledError` propagates; `finally` cleans `active_tasks`; singleton lock released. Status already persisted as STOPPED.

### 5.7 DB sessions

- Executor uses its **own** `SessionLocal()` sessions (not FastAPI `Depends`) — matches IMPROVEMENT_FEATURE.md §11 ("persistence: own DB sessions, avoids transaction lifetime issues").
- Each loop iteration opens + commits + closes its own session; never hold a session across `await`.

### 5.8 Event broadcasting hook (Phase 7 wires the socket)

```python
async def _broadcast(self, event_type: str, mission_id: int, extra: dict | None = None):
    payload = {"type": event_type, "mission_id": mission_id, **({"data": extra} if extra else {})}
    await manager.broadcast("mission", payload)   # no-op when no subscribers
```

### 5.9 Repository additions

`MissionRepository`:
```python
def get_running_count(self) -> int                    # count status == 'RUNNING'
def set_status(self, mission_id, status) -> Mission   # persist status + commit
```

`MissionLocationRepository`:
```python
def get_next_pending(self, mission_id) -> MissionLocation | None
    # status == 'PENDING', sequence_order not null, order by sequence_order asc, first
def mark_visited(self, mission_id, location_id, scan_session_id) -> None
def has_planned_locations(self, mission_id) -> bool
```

### 5.10 Settings (defaults; documented fully in Phase 10)

| Key | Default | Purpose |
|-----|---------|---------|
| `MISSION_POLL_INTERVAL` | 2 (s) | Loop sleep between GPS checks |
| `MISSION_GPS_FAILURE_THRESHOLD` | 10 | Consecutive GPS failures → FAILED |
| `MISSION_CLI_TIMEOUT` | 30 (s) | Scan timeout during mission |
| `MISSION_START_GPS_TIMEOUT` | 5 (s) | GPS availability gate at start |
| `MISSION_LOG_SIZE` | 200 | Ring buffer size per mission |
| `MISSION_DEFAULT_RADIUS_METERS` | 20 | Radius when mission.radius_meters is null |

### 5.11 Error message catalog (English)

| Condition | Status | Message |
|-----------|--------|---------|
| Mission not found | 404 | `Mission not found` |
| Another mission running | 409 | `Another mission is already running` |
| Same mission task active | 409 | `Mission is already running` |
| Bad start status | 409 | `Cannot start mission while it is <status>` |
| No plan | 422 | `Mission has no planned locations. Run plan first` |
| GPS unavailable at start | 503 | `GPS not available` |
| Wrong state pause/resume/stop | 409 | `Cannot pause/resume/stop mission while it is <status>` |

---

## 6. Acceptance Criteria

### 6.1 Unit tests

Fixtures: `MockGPSProvider` (sequence of coords, fail-N-times mode) + fake CLI adapter returning canned results.

| # | Test | Expectation |
|---|------|-------------|
| U01 | `start` on mission with plan | Status RUNNING, task registered, `started_at` set |
| U02 | `start` second mission while first runs | 409 `Another mission is already running` |
| U03 | `start` without plan | 422 `Mission has no planned locations. Run plan first` |
| U04 | `start` GPS timeout | Status FAILED, 503 `GPS not available` |
| U05 | Full run (2 targets) | Both VISITED, `visited_locations==2`, `current_location_id` set, `scan_session_id` linked, status COMPLETED, task removed |
| U06 | Geofence miss | Target stays PENDING; loop continues |
| U07 | Scan error (CLI raises) | Target SKIPPED; mission still RUNNING; `SCAN_ERROR` logged |
| U08 | GPS failure threshold | After N failures → FAILED; `FAILED` logged |
| U09 | `pause` then `resume` | PAUSED persists; resume returns RUNNING; loop resumes |
| U10 | `stop` | Status STOPPED, `stopped_at` set, task cancelled/removed |
| U11 | `startup` restore | STARTING/RUNNING/PAUSED rows → STOPPED with `stopped_at`; IDLE/READY untouched |
| U12 | Log ring buffer | maxlen honored; newest last |
| U13 | tty fallback | Mission without tty_port logs fallback + uses `DEFAULT_TTY` |
| U14 | `shutdown` cancels tasks | active_tasks empty, no exceptions |

### 6.2 End-to-end / integration tests

| # | Test | Expectation |
|---|------|-------------|
| E01 | create → upload → plan → start → auto-complete | Full lifecycle ends COMPLETED with scans linked (mock GPS walks through towers) |
| E02 | Concurrent start x2 (asyncio) | Second gets 409 |
| E03 | pause/resume/stop via HTTP | Status transitions correct via `/status` |
| E04 | `/logs` during run | Events appear with timestamps |
| E05 | App restart simulation | `startup()` turns STARTING/RUNNING/PAUSED → STOPPED; executor idle |
| E06 | `/start` on COMPLETED mission | 409 `Cannot start mission while it is COMPLETED` |
| E07 | Full `pytest` suite | All existing tests still pass (no regressions) |

### 6.3 Verification commands

```bash
cd ~/Cellular-Discovery-Service/backend

# With GPS_PROVIDER=mock in .env and a fake/mock CLI path, or run the test suite:
.venv/bin/pytest -q tests/test_executor.py

# Manual smoke (requires GPS available / mock):
curl -s -X POST http://localhost:8000/api/v1/missions/1/start
curl -s http://localhost:8000/api/v1/missions/1/status
curl -s http://localhost:8000/api/v1/missions/1/logs
curl -s -X POST http://localhost:8000/api/v1/missions/1/pause
curl -s -X POST http://localhost:8000/api/v1/missions/1/resume
curl -s -X POST http://localhost:8000/api/v1/missions/1/stop
```

---

### Checklist

- [ ] `MissionExecutor` singleton with `asyncio.Lock`
- [ ] `active_tasks` map + shutdown cleanup
- [ ] Startup restore STARTING/RUNNING/PAUSED → STOPPED
- [ ] start/pause/resume/stop/status/logs endpoints
- [ ] GPS polling via `asyncio.to_thread`, failure threshold → FAILED
- [ ] Scan errors non-fatal (SKIP + continue)
- [ ] tty override with `DEFAULT_TTY` fallback logging
- [ ] Own DB sessions (no `Depends` inside loop)
- [ ] In-memory ring-buffer logs
- [ ] WS broadcast hooks (no-op without subscribers)
- [ ] All Acceptance Criteria (U01–U14, E01–E07) pass
