# FEATURE_IMPROVEMENT_10_EDGE_CASES_CONFIG.md

> Mission Planner Epic — Phase 10: Edge Cases & Configuration (final)

| Field | Value |
|-------|-------|
| **Epic** | Mission Planner (epic/) |
| **Phase** | 10 of 10 |
| **Dependencies** | Phases 01–09 (cross-reference / aggregation) |
| **Estimated LOC** | ~300 |
| **Complexity** | Low |
| **Status** | Draft |
| **Target** | Dev backend at `~/Cellular-Discovery-Service/backend` |

---

## 📑 Table of Contents

1. [Goals](#1-goals)
2. [Backend Tasks](#2-backend-tasks)
3. [File Changes](#3-file-changes)
4. [Configuration Additions](#4-configuration-additions)
5. [Edge Case Matrix](#5-edge-case-matrix)
6. [Logging Standards](#6-logging-standards)
7. [Acceptance Criteria](#7-acceptance-criteria)

---

## 1. Goals

- Document every cross-cutting edge case and its mitigation, aggregated from all phases, in one reference.
- Add all mission configuration keys to `Settings` (with validation) + `.env.example`.
- Settle remaining **open decisions** that the earlier phases left implicit:
  1. Re-running a `STOPPED`/`FAILED` mission (re-plan path).
  2. Restart recovery must also cover `STARTING` and `PAUSED` leftovers (not only `RUNNING`).
  3. `failed_reason` lives in executor logs only (no schema column) — schema stays as Phase 1.
- Standardize logging for mission events so failures are diagnosable in systemd journal.

---

## 2. Backend Tasks

1. [ ] Add mission settings to `app/config/settings.py` (with `Field(gt=0, ...)` validation).
2. [ ] Update `.env` (dev) and `.env.example` with the new keys + comments.
3. [ ] Apply **Open Decision 1**: allow `POST /{id}/plan` when status is `IDLE`, `PLANNING`, `READY`, `STOPPED`, or `FAILED` (all non-active); planning resets to `PLANNING` → `READY`. Update Phase-4 router guard + doc.
4. [ ] Apply **Open Decision 2**: executor `startup()` restores any mission with status in `{STARTING, RUNNING, PAUSED}` → `STOPPED`. Update Phase-6 doc + code.
5. [ ] Apply **Open Decision 3**: no `failed_reason` column; reason recorded via `_log(..., "FAILED", reason)` + Python logger. Confirmed no Phase-1 migration change.
6. [ ] Run full test suite (no regressions).

---

## 3. File Changes

### Modified files
| Path | Description |
|------|-------------|
| `backend/app/config/settings.py` | Mission settings fields + validation |
| `backend/.env` / `backend/.env.example` | New keys documented |
| `backend/app/api/routers/mission_planning.py` | Allow `STOPPED`/`FAILED` in plan guard (Decision 1) |
| `backend/app/core/mission_executor.py` | `startup()` restore `{STARTING, RUNNING, PAUSED}` (Decision 2) |
| `epic/FEATURE_IMPROVEMENT_04_PLANNER_ALGORITHM.md` | §4.1 allowed-status update |
| `epic/FEATURE_IMPROVEMENT_06_BACKGROUND_EXECUTOR.md` | §5.1 `startup()` update |

---

## 4. Configuration Additions

### 4.1 `Settings` fields

```python
from pydantic import Field

class Settings(BaseSettings):
    # ...existing...

    # ---- Mission Planner ----
    MISSION_POLL_INTERVAL: int = Field(default=2, gt=0, description="Seconds between GPS checks while mission RUNNING")
    MISSION_GPS_FAILURE_THRESHOLD: int = Field(default=10, gt=0, description="Consecutive GPS failures before mission is marked FAILED")
    MISSION_CLI_TIMEOUT: int = Field(default=30, gt=0, description="Per-scan timeout during mission execution")
    MISSION_START_GPS_TIMEOUT: int = Field(default=5, gt=0, description="GPS availability gate at mission start")
    MISSION_LOG_SIZE: int = Field(default=200, gt=0, description="Ring-buffer size for per-mission event logs")
    MISSION_DEFAULT_RADIUS_METERS: int = Field(default=20, gt=0, description="Geofence radius when mission.radius_meters is null")
    MISSION_MAX_LOCATIONS: int = Field(default=10_000, gt=0, description="Max CSV rows per location upload")
```

### 4.2 `.env.example` additions

```env
# ---- Mission Planner Settings ----
MISSION_POLL_INTERVAL=2
MISSION_GPS_FAILURE_THRESHOLD=10
MISSION_CLI_TIMEOUT=30
MISSION_START_GPS_TIMEOUT=5
MISSION_LOG_SIZE=200
MISSION_DEFAULT_RADIUS_METERS=20
MISSION_MAX_LOCATIONS=10000
```

### 4.3 Validation behavior

- `gt=0` → invalid `.env` value raises pydantic `ValidationError` at startup (`get_settings()`), failing fast instead of silently misbehaving at runtime.
- Defaults are safe for production (no changes required to existing deployments; keys are optional).

---

## 5. Edge Case Matrix

> Aggregated reference. `Guard` = API-level; `DB` = constraint-level; `Executor` = runtime-level.

| # | Scenario | Phase | Level | Handling |
|---|----------|-------|-------|----------|
| E1 | Duplicate `cellular_tower_id` in CSV / DB (same mission) | 2 | DB/Service | UPSERT (update, not insert); `UNIQUE (mission_id, cellular_tower_id)` |
| E2 | Invalid / out-of-range coordinates in CSV | 2 | Service | Row-level error entry; valid rows still inserted; DB CHECK as backstop |
| E3 | Empty CSV / no valid rows | 2 | Service | 422 `CSV file is empty or has no valid rows` |
| E4 | CSV > `MISSION_MAX_LOCATIONS` | 2 | Service | 422 `CSV file exceeds maximum of {limit} rows` |
| E5 | Location upload/delete while mission STARTING/RUNNING/PAUSED | 2,3 | Guard | 409 `Cannot modify locations while mission is running` |
| E6 | Deleting a location referenced as start/current | 1,3 | DB | `ON DELETE SET NULL` auto-clears `missions.start_location_id`/`current_location_id` |
| E7 | Plan/start a mission with zero locations | 4,6 | Guard | 422 `Mission has no planned locations...` / `Mission has no locations to plan` |
| E8 | Structural PATCH (radius/tty/start) after planning | 3 | Service | Clears all `sequence_order` → mission must be re-planned (status stays; plan resets to READY) |
| E9 | Manual reorder vs auto-plan | 4 | Service | Manual order persists until next `POST /plan`; plan always overwrites |
| E10 | Reorder list incomplete / duplicate / foreign location | 4 | Service | 422 with specific English messages |
| E11 | Concurrent mission start | 6 | Guard | 409 `Another mission is already running` (asyncio lock + DB count) |
| E12 | GPS unavailable at start | 6 | Guard | 503 `GPS not available`; mission → FAILED |
| E13 | GPS loss mid-run | 6 | Executor | Consecutive failures ≥ `MISSION_GPS_FAILURE_THRESHOLD` → FAILED; else retry each poll |
| E14 | Single scan failure (CLI error) | 6 | Executor | Non-fatal: location → SKIPPED, log `SCAN_ERROR`, emit `mission_skipped`, loop continues |
| E15 | `scan_session_id` 1-to-1 collision | 1 | DB | `UNIQUE` on `mission_locations.scan_session_id`; duplicate insert fails gracefully |
| E16 | App restart with mission in flight | 6 | Executor | `startup()` restores `{STARTING, RUNNING, PAUSED}` → STOPPED (+`stopped_at`) |
| E17 | Delete mission while active | 3 | Guard | 409 (STARTING/RUNNING/PAUSED); delete cascade only when non-active |
| E18 | Mission deleted (allowed states) | 3 | DB | CASCADE removes `mission_locations`; linked `scan_sessions` kept (`SET NULL`) |
| E19 | No `tty_port` override on mission | 6 | Executor | Fallback `DEFAULT_TTY` + warning log |
| E20 | WS mission broadcast with zero subscribers | 7 | Executor | No-op, loop unaffected |
| E21 | Re-run a STOPPED/FAILED mission | 10 | Guard | **Decision 1:** plan allowed from `STOPPED`/`FAILED` (reset → READY) then start |
| E22 | STOPPED/FAILED mission has partial visits | 6,10 | Executor | Visited locations stay `VISITED`; next plan resets non-visited to PENDING (already covered by `update_sequence_batch`) |
| E23 | Legacy/manual scans have no mission link | 5,8 | DB | `mission_location_id` nullable; excluded from mission-scoped queries |

---

## 6. Logging Standards

### 6.1 Logger hierarchy

```
app.core.mission_executor      # executor lifecycle + loop
app.api.routers.mission_*      # request-level (start/pause/stop failures)
app.services.location_service  # CSV upload summaries + row errors
app.services.mission_planner   # planning runs
```

- All under root `logging.basicConfig(level=settings.LOG_LEVEL)` (already in `main.py`).
- Use `logger = logging.getLogger(__name__)` in every module.

### 6.2 Mission event log (ring buffer) vs Python logger

| Concern | Destination |
|---------|-------------|
| Machine-readable mission timeline (STARTING, VISITED, COMPLETED, FAILED…) | executor ring buffer → `GET /missions/{id}/logs` |
| Operability/debugging | Python logger → systemd journal / stdout |
| Both should carry the same `event_type` vocabulary (Phase 7) |

### 6.3 Rules

- **Never** log secrets (DB password, .env contents).
- Log `mission_id` and `location_id`/`tower_id` in every mission event line for greppability.
- Fallback-to-DEFAULT_TTY is a `warning` (per IMPROVEMENT_FEATURE.md §11).
- Fatal errors include the exception traceback (`logger.exception`).
- Non-fatal scan errors: `error` level with tower context, then continue.

---

## 7. Acceptance Criteria

### 7.1 Unit tests

| # | Test | Expectation |
|---|------|-------------|
| U01 | Settings defaults | New keys match table §4.1 when `.env` absent |
| U02 | Settings validation | `MISSION_POLL_INTERVAL=0` raises `ValidationError` |
| U03 | Plan guard accepts STOPPED/FAILED | 200; status resets PLANNING→READY |
| U04 | Plan guard still rejects RUNNING/PAUSED/STARTING | 409 |
| U05 | `startup()` restores STARTING/RUNNING/PAUSED | All → STOPPED with `stopped_at`; IDLE/READY untouched |
| U06 | Re-run flow (STOPPED → plan → start) | Mission executes again; visited stays; non-visited re-planned |
| U07 | `.env.example` keys | Match §4.2 exactly |

### 7.2 End-to-end / integration tests

| # | Test | Expectation |
|---|------|-------------|
| E01 | Stop a running mission, then re-plan + re-start | Completes second time; logs show STOPPED then new STARTING |
| E02 | Simulate crash: set status STARTING in DB, run `startup()` | Becomes STOPPED |
| E03 | Logs include tower context + fallback warning | Grep-able via journal/`/logs` |
| E04 | Full `pytest` suite | All existing + new tests pass (no regressions) |

### 7.3 Verification commands

```bash
cd ~/Cellular-Discovery-Service/backend

# Settings sanity
.venv/bin/python -c "from app.config.settings import get_settings; s=get_settings(); \
print(s.MISSION_POLL_INTERVAL, s.MISSION_DEFAULT_RADIUS_METERS, s.MISSION_MAX_LOCATIONS)"

# Invalid value should fail fast
MISSION_POLL_INTERVAL=0 .venv/bin/python -c "from app.config.settings import get_settings; get_settings()" && echo "SHOULD HAVE FAILED" || echo "failed fast: OK"

# Full sweep
.venv/bin/pytest -q
```

---

### Checklist

- [ ] Settings fields + validation added
- [ ] `.env` / `.env.example` updated
- [ ] Decision 1: plan allowed from STOPPED/FAILED (code + Phase-4 doc)
- [ ] Decision 2: startup restores {STARTING, RUNNING, PAUSED} (code + Phase-6 doc)
- [ ] Decision 3: failed_reason in logs only — confirmed
- [ ] Edge matrix E1–E23 covered by tests (no gaps)
- [ ] Logging standards applied
- [ ] All Acceptance Criteria (U01–U07, E01–E04) pass
