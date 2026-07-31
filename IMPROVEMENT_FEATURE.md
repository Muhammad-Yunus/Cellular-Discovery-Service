# IMPROVEMENT_FEATURE.md — Mission Planner System Analysis & Design

## 📖 1. Overview

### Background
Existing system allows manual LTE scans via `/scan` endpoint and records session history with GPS location.  
The new **Mission Planner** feature extends this to automate field scan workflows using external tower data from a Tower Management System (TMS), turning it into an autonomous drone/travel-based mapping tool.

### High-Level Flow
```
Tower Management System (External) → CSV export (tower_lat, lon, id, name) 
    → POST /api/v1/missions/{id}/locations/upload (CSV import)
    → Create mission reference locations
    → Auto-planner orders visit sequence OR user manually reorders
    → Mission executor (background asyncio loop) polls GPS via UART/NMEA
    → When within radius of target tower → auto-trigger scan
    → Scan result linked back to mission location (1-to-1)
    → Broadcast progress via WebSocket
    → Mission status: IDLE→STARTING→RUNNING→COMPLETED|STOPPED|FAILED
    → On app restart: missions left in STARTING/RUNNING/PAUSED become STOPPED (user manual recovery)
```

**Key constraint:** Only ONE mission can be `RUNNING` at any time (singleton executor). Concurrent requests are rejected.

---

## 🏗️ 2. Database Schema Design

### 2.1 Existing Tables (NO modifications except additive nullable columns)

| Table | Schema | Description |
|-------|--------|-------------|
| `scan_sessions` | `app` | Scan header (tty_port, latitude, longitude, created_at) — **add `mission_location_id` (nullable)** |
| `scan_results` | `app` | Scan detail with operator_name, mcc, mnc, rat, status, session_id FK |
| `settings` | `app` | Key-value configuration (DEFAULT_TTY, SCAN_TIMEOUT, etc.) |

**Critical:** All modifications are `ADD COLUMN IF NOT NULL`. Zero breaking changes.

### 2.2 New Tables

> **Design note (revised):** `mission_locations` is **per-mission** detail data (one row per CSV line uploaded for a mission). The ordered visit sequence (`sequence_order`, `status`, `scan_session_id`, distance/bearing) lives **directly on `mission_locations`**. A separate `mission_planners` table is **not needed** — those columns are folded into `mission_locations`.

#### A. `missions` — Mission header (master)

Single row per mission, tracks overall state and counters.

```sql
CREATE TABLE app.missions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'IDLE' CHECK (status IN ('IDLE','PLANNING','READY','STARTING','RUNNING','PAUSED','COMPLETED','STOPPED','FAILED')),
    radius_meters INTEGER DEFAULT 20 CHECK (radius_meters > 0),
    tty_port VARCHAR(50),                               -- Override from settings, nullable
    start_location_id INTEGER,                          -- FK → app.mission_locations(id) (added via ALTER)
    current_location_id INTEGER,                        -- FK → app.mission_locations(id) (added via ALTER)
    total_locations INTEGER DEFAULT 0,
    visited_locations INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_missions_status ON app.missions(status);
CREATE INDEX idx_missions_start_loc ON app.missions(start_location_id);
CREATE INDEX idx_missions_current_loc ON app.missions(current_location_id);
```

#### B. `mission_locations` — Detail rows (1-to-many with `missions`)

Each row = 1 line from the CSV uploaded for a mission. Doubles as the visit plan.

```sql
CREATE TABLE app.mission_locations (
    id SERIAL PRIMARY KEY,
    mission_id INTEGER NOT NULL REFERENCES app.missions(id) ON DELETE CASCADE,
    cellular_tower_id VARCHAR(100) NOT NULL,            -- External TMS id (unique per mission)
    cellular_tower_name VARCHAR(255),
    latitude FLOAT NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude FLOAT NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    upload_batch_id VARCHAR(36),                        -- Group rows from one CSV upload
    sequence_order INTEGER,                             -- Planned visit order (null = unplanned)
    status VARCHAR(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING','IN_PROGRESS','VISITED','SKIPPED')),
    distance_from_previous_meters FLOAT,
    bearing_from_previous_degrees FLOAT,
    estimated_arrival_time TIMESTAMPTZ,
    actual_visit_time TIMESTAMPTZ,
    scan_session_id INTEGER UNIQUE REFERENCES app.scan_sessions(id) ON DELETE SET NULL,  -- 1-to-1 nullable
    visited_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_mission_location_tower UNIQUE (mission_id, cellular_tower_id)
);

CREATE INDEX idx_mission_locations_mission ON app.mission_locations(mission_id);
CREATE INDEX idx_mission_locations_sequence ON app.mission_locations(mission_id, sequence_order);
CREATE INDEX idx_mission_locations_status ON app.mission_locations(status);
CREATE INDEX idx_mission_locations_scan_session ON app.mission_locations(scan_session_id);
CREATE INDEX idx_mission_locations_batch ON app.mission_locations(upload_batch_id);
```

**Circular FK resolution:** `missions.start_location_id` / `current_location_id` point back to `mission_locations`, so create `missions` first without those two FKs, create `mission_locations`, then `ALTER TABLE app.missions ADD CONSTRAINT fk_missions_start_location FOREIGN KEY (start_location_id) REFERENCES app.mission_locations(id) ON DELETE SET NULL` (same for `current_location_id`).

**Note:** `scan_session_id` in `mission_locations` enforces **1-to-1 with scan_sessions**. Since it's `UNIQUE`, each scan session can be linked to at most one location visit. Conversely, `mission_location_id` added to `scan_sessions` is optional (for backward compatibility).

---

## 3️⃣ 3. API Design (All under `/api/v1/missions/`)

### 3.1 Location Management (Tower Import)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/missions/{id}/locations/upload` | Multipart/form-data CSV upload for a mission, returns batch metadata |
| `GET`  | `/missions/{id}/locations` | Paginated list with search/filter by cellular_tower_id/name |
| `GET`  | `/missions/{id}/locations/{location_id}` | Single location detail |
| `DELETE` | `/missions/{id}/locations/{location_id}` | Delete single location (blocked if mission is RUNNING) |
| `POST` | `/missions/{id}/locations/bulk-delete` | Delete by upload_batch_id (cleanup) |

**CSV format required (header row mandatory):**
```
cellular_tower_id,cellular_tower_name,latitude,longitude
TWR-001,Jakarta Pusat,-6.2088,106.8456
TWR-002,Jakarta Selatan,-6.2615,106.8106
```

**Upload response:**
```json
{
  "upload_batch_id": "e5c7f2a4-b8d9-4e3f-a1b2-c3d4e5f6a7b8",
  "total_rows": 50,
  "inserted": 47,
  "updated": 2,
  "skipped": 1,
  "errors": [
    {"row": 7, "error": "Invalid latitude: abc"}
  ]
}
```
**UPSERT strategy:** If `cellular_tower_id` exists, update name/location; else insert.

### 3.2 Mission CRUD

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/` | Create mission draft (assigns start_location, total_locations=0) |
| `GET`  | `/` | List missions, filterable by status, name |
| `GET`  | `/{id}` | Get mission detail + locations (nested route) |
| `PATCH`| `/{id}` | Update name, description, radius, tty_port (override) |
| `DELETE`| `/{id}` | Delete only when IDLE/READY/STOPPED |

**Create request:**
```json
{
  "name": "Jakarta Utara Sweep",
  "description": "Scan during drone testing",
  "start_location_id": 1,
  "radius_meters": 20,
  "tty_port": "/dev/ttyUSB1"  // Optional, override DEFAULT_TTY
}
```

### 3.3 Planning Endpoint

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/{id}/plan` | Generate auto-plan nearest-neighbor order |
| `GET`  | `/{id}/route` | Get current planned route (ordered by sequence_order) |
| `POST` | `/{id}/route/reorder` | Manual sequence reordering (send array of `[location_id, sequence_order]`) |
| `POST` | `/{id}/route/skip` | Mark specific location as SKIPPED |

**Auto-planner algorithm:** Nearest-Neighbor from start_location, then 2-opt local optimization for refinement. Output updates `mission_locations.sequence_order` and computes `distance_from_previous_meters`, `bearing_from_previous_degrees`.

**Manual reorder request body:**
```json
[{"mission_location_id": 5, "sequence_order": 1}, {"mission_location_id": 2, "sequence_order": 2}]
```

### 3.4 Execution Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/{id}/start` | Transition READY/IDLE → STARTING → RUNNING |
| `POST` | `/{id}/pause` | RUNNING → PAUSED |
| `POST` | `/{id}/resume` | PAUSED → RUNNING |
| `POST` | `/{id}/stop` | Any → STOPPED |
| `GET`  | `/{id}/status` | Live status + current_location_id + visited/total |
| `GET`  | `/{id}/logs` | Event log (JSON array of {timestamp, event_type, message}) |

### 3.5 Mission-Scoped Scan History

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/{id}/scans` | List all scan_sessions for this mission (paginated) |
| `GET`  | `/{id}/scans/export` | CSV export scoped to mission |

---

## 🔁 4. State Machine (Mission Status)

```
                     ┌── PLANNING ──┐
                    └───────┬───────┘
                     ┌──────▼──────┐     ┌─────────────┐
                 IDLE │           │◄────│   STARTING    │◄──┐
                     │ (create)    │     │ (GPS check)   │   │
                     └──────┬──────┘     └─────────────┘   │
                            │                                 
                            ▼                               
                      ┌──────────┐                           
                      │   READY  │◄──(generate plan)          
                      └────┬─────┘                            
                           │                                   
                           ▼                               
                     ┌──────────┐                          
                     │ RUNNING  │──────────► COMPLETED      
                     │ (executor)│         (all visited)     
                     └────┬─────┘                          
                          ���                                   
                          ├───► STOPPED ←───┬ (user stop)   
                          │                 │               
                          ├─── FAILED ◄─────┴── (error)     
                          │                                 
                          ├─► PAUSED (user pause)          
                          │        │                       
                          │        └──► RUNNING (resume)   
                          │                                 
                          └───► STOPPED (manual abort)     
```

**Transition rules:**
- `IDLE` → `PLANNING`: on `POST /plan`
- `PLANNING` → `READY`: on completion of planning (auto)
- `STOPPED`/`FAILED` → `PLANNING`: on `POST /plan` (re-plan; already-completed visits are preserved)
- `READY` → `STARTING`: on `POST /start`
- `STARTING` → `RUNNING`: after confirming GPS is available within timeout (5s default)
- `STARTING` → `FAILED`: GPS unavailable within timeout
- `RUNNING` → `COMPLETED`: all locations reached
- `RUNNING` → `STOPPED`: on `POST /stop` or app shutdown
- `RUNNING` → `PAUSED`: on `POST /pause`
- `PAUSED` → `RUNNING`: on `POST /resume`
- `RUNNING` → `FAILED`: fatal error (GPS lost N times, modem hang)
- Any → `STOPPED`: on `POST /stop`
- Any → `FAILED`: database corruption or critical error

**Concurrency constraint:** Only one mission at a time may be in `RUNNING` state. Singleton executor checks `SELECT COUNT(*) FROM missions WHERE status='RUNNING' BEFORE starting new one → if > 0, reject with 409 Conflict.

---

## ⚙️ 5. Background Executor Architecture

### 5.1 Singleton Pattern
A single `MissionExecutor` singleton (initialized at app startup in `lifespan`) maintains a dict `active_missions: Dict[int, asyncio.Task]` mapping `mission_id` to background task. It also holds an `asyncio.Lock` (`executor_lock`) to ensure single-concurrent-mission discipline.

### 5.2 Mission Loop Pseudocode

```python
class MissionExecutor:
    def __init__(self):
        self.active_tasks: dict[int, asyncio.Task] = {}
        self.lock = asyncio.Lock()
        self.gps_provider = create_gps_provider(settings.GPS_PROVIDER)
        
        # On app load, restore missions left in STARTING/RUNNING/PAUSED to STOPPED
        async def restore_running():
            db = get_db()
            for m in db.query(Mission).where(Mission.status.in_(['STARTING', 'RUNNING', 'PAUSED'])).all():
                m.status = 'STOPPED'
                m.stopped_at = now()
            db.commit()

    async def run_mission(self, mission_id: int):
        lock_acquired = await self.lock.acquire()
        try:
            mission = self._get_mission(mission_id)
            if mission.status not in {'STARTING', 'RUNNING'}:
                return
            
            mission.status = 'RUNNING'
            mission.started_at = datetime.now(tz=UTC)
            
            while mission.status == 'RUNNING':
                # Check pause flag
                if mission.is_paused:
                    break
                
                # Get current GPS
                try:
                    loc = self.gps_provider.get_location()
                except GPSError as e:
                    mission.failure_count += 1
                    if mission.failure_count >= settings.GPS_FAILURE_THRESHOLD:
                        mission.status = 'FAILED'
                        mission.failed_reason = str(e)
                        break
                    await asyncio.sleep(MISSION_POLL_INTERVAL)
                    continue
                
                # Find next pending location
                location = self._get_next_pending(mission.id)
                if not location:
                    mission.status = 'COMPLETED'
                    mission.completed_at = datetime.now(tz=UTC)
                    break
                
                # Distance calculation
                lat2, lon2 = location.latitude, location.longitude
                dist = haversine(loc.latitude, loc.longitude, lat2, lon2)
                
                # Within radius? Trigger scan
                if dist <= mission.radius_meters:
                    # Determine tty port
                    port = mission.tty_port or settings.DEFAULT_TTY
                    if mission.tty_port is None:
                        logger.warning(f"Fallback to DEFAULT_TTY={port} for mission {mission.id}")
                    
                    try:
                        scan_result = self._trigger_scan(port, loc.latitude, loc.longitude, mission.id, location.id)
                        location.scan_session_id = scan_result.id
                        location.status = 'VISITED'
                        location.actual_visit_time = datetime.now(tz=UTC)
                        location.visited_at = datetime.now(tz=UTC)
                        mission.visited_locations += 1
                        mission.current_location_id = location.id
                        
                        # Broadcast WS event
                        ws_manager.broadcast('mission', {
                            'type': 'mission_visit',
                            'mission_id': mission.id,
                            'data': {
                                'location_id': location.id,
                                'scan_session_id': scan_result.id,
                                'distance_m': round(dist, 2),
                            },
                        })
                        
                        # Advance to next pending
                    except CLIError as e:
                        logger.error(f"Scan failed for mission {mission.id}: {e}")
                        # Continue to next, don't fail mission
                
                mission.updated_at = datetime.now(tz=UTC)
                
                await asyncio.sleep(MISSION_POLL_INTERVAL  # e.g., 2 seconds
        
        finally:
            self.lock.release()
    
    def _trigger_scan(self, port: str, lat: float, lon: float, mission_id: int, location_id: int) -> ScanResult:
        """Execute scan and save result with reference."""
        db = SessionLocal()
        try:
            # Call scan_service with optional mission location reference
            service = ScanService(db=db)
            session = service.execute_scan_with_mission_ref(
                port=port,
                latitude=lat,
                longitude=lon,
                mission_location_id=location_id,
                timeout=settings.MISSION_CLI_TIMEOUT
            )
            return session
        except Exception:
            raise
        finally:
            db.close()
```

### 5.3 Scan Service Extension

Modify `ScanService.execute_scan()` to accept optional `mission_location_id: int | None = None`. This value gets stored in the newly added `mission_location_id` column on `scan_sessions`. The modified signature must remain backward-compatible (keyword-only with default).

---

## 6️⃣ 6. WebSocket Real-Time Events

New channel `"mission"` with events matching those above (event types listed in section 3.5 JSON response). These complement existing `"gps"` and `"scan"` channels without modification.

Event payload structure:

```json
{
  "type": "mission_progress",
  "mission_id": 123,
  "data": {
    "current_location_id": 45,
    "visited_locations": 3,
    "total_locations": 10,
    "status": "RUNNING",
    "distance_to_target_meters": 15.2
  }
}
```

> `mission_id` is always **top-level** on mission events (never duplicated inside `data`).

Same pattern for `mission_visit`, `mission_completed`, `mission_failed`, `mission_stopped`.

---

## 7️⃣ 7. Edge Cases & Mitigation

| Scenario | Handling |
|----------|----------|
| CSV upload duplicates `cellular_tower_id` | UPSERT (update row) instead of insert |
| GPS failure while executing | Retry N times (configurable), then FAIL |
| Multiple users request concurrent mission start | Reject with 409 Conflict: "Another mission already running" |
| Mission deleted while RUNNING | Background executor detects on next loop iteration; cleanup orphaned task |
| User modifies mission location after planning | Invalidate sequence_order (set to need regenerate) on PATCH |
| Manual reorder conflicts with auto-plan | Manual overrides take precedence; auto-plan clears any previous plan first |
| Mission location scan_session_id already taken | UNIQUE constraint enforces 1-to-1; duplicate fails gracefully |
| App restarts during a mission in STARTING/RUNNING/PAUSED | Restore → STOPPED on startup; user must manually restart |
| Location referenced by multiple missions | Allowed; UPSERT safe |
| Mission with no locations | Return 422 when attempting to start/planning |
| Location deleted while mission referencing | RESTRICT FK prevent deletion; remove manually first |

---

## 8️⃣ 8. Implementation Phases

| Phase | Scope | Deliverables |
|-------|-------|--------------|
| **Phase 1** | Data Model | Add tables `missions`, `mission_locations`; add `mission_location_id` to `scan_sessions`; migrate via Alembic |
| **Phase 2** | Location CRUD | Backend models, repositories, schemas, endpoints `/missions/{id}/locations/*`, CSV upload endpoint, UPSERT logic |
| **Phase 3** | Mission CRUD | Models, services, CRUD endpoints, status fields, TTL logging |
| **Phase 4** | Planner | Nearest-neighbor + 2-opt algorithm, auto-planner endpoint `/plan`, manual `/route/reorder`, Haversine utility module |
| **Phase 5** | Scanner Integration | Modify `ScanService.execute_scan()` to accept `mission_location_id`; extend `ScanSessionResponse` to include `mission_location_id` |
| **Phase 6** | Executor | Singleton `MissionExecutor`, background `asyncio` loop, GPS polling, scan trigger, mission state transitions, concurrency lock |
| **Phase 7** | WebSockets | New `/ws/mission` channel, broadcast events from executor |
| **Phase 8** | Mission Scoped Queries | Add `/missions/*/scans` and `/exports` endpoints |
| **Phase 9** | Testing | Unit tests for algorithms, integration tests for full flow, edge case tests |
| **Phase 10** | Documentation | This document + update API.md/FE_SPEC.md (post-phase) |

---

## 9️⃣ 9. Configuration Additions (.env)

Add these keys to `.env.example`:

```env
# Mission Planner Settings
MISSION_POLL_INTERVAL=2          # Seconds between GPS checks while mission RUNNING
MISSION_GPS_FAILURE_THRESHOLD=10 # Consecutive failures before marking mission FAILED
MISSION_DEFAULT_RADIUS_METERS=20 # Default geofence radius if none specified per mission
MISSION_CLI_TIMEOUT=30           # Timeout for individual scan during mission execution
MISSION_START_GPS_TIMEOUT=5      # GPS availability gate at mission start
MISSION_LOG_SIZE=200             # Ring-buffer size for per-mission event logs
MISSION_MAX_LOCATIONS=10000      # Max CSV rows per location upload
```

---

## 🔟 10. Backward Compatibility Summary

All changes are **non-breaking**:

✅ New tables do not affect existing queries  
✅ Added `mission_location_id` to `scan_sessions` is **nullable**, so old records stay valid  
✅ Existing API endpoints unchanged (no path/version changes)  
✅ Pydantic schemas: new fields are optional (default None) in existing response models if extended  
✅ Background processes are independent add-ons, no impact on core scan workflow  

---

## 11️⃣ 11. Technology Notes

- **Haversine implementation:** Use simple pure-Python formula (no external lib needed) — see `utils.geo.haversine(lat1, lon1, lat2, lon2)` helper returning distance in meters.
- **2-opt refinement:** Optional post-processing of nearest-neighbor output; O(n²) complexity acceptable for n < 200 locations.
- **Concurrency control:** Single `asyncio.Lock` + global flag check ensures only one RUNNING mission. For future scaling, use DB-level advisory locks (`pg_advisory_lock`).
- **Persistence:** Background executor creates its own DB sessions (`SessionLocal()`) — not Depends injection — to avoid transaction lifetime issues.
- **Error handling:** Non-fatal errors (single scan fail) log and continue; fatal errors (GPS loss, command not found) transition mission to FAILED.
- **Logging:** Standard Python logging, level from settings. Warn when mission falls back to `DEFAULT_TTY`.

---

*Document version 1.0 | Date: 2025-07-31 | Author: Agnes-2.0-Flash (Sapiens AI)*
