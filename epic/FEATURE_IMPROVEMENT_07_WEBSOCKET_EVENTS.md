# FEATURE_IMPROVEMENT_07_WEBSOCKET_EVENTS.md

> Mission Planner Epic — Phase 7: WebSocket Real-Time Mission Events

| Field | Value |
|-------|-------|
| **Epic** | Mission Planner (epic/) |
| **Phase** | 7 of 10 |
| **Dependencies** | [06_BACKGROUND_EXECUTOR](FEATURE_IMPROVEMENT_06_BACKGROUND_EXECUTOR.md) |
| **Estimated LOC** | ~260 |
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

- Add a `mission` WebSocket channel: `GET /ws/mission`.
- Define canonical event payloads for the full mission lifecycle (started, progress, visit, pause, resume, stop, completed, failed, skipped).
- Wire the Phase-6 executor broadcasts to a single helper (`broadcast_mission_event`) so payload shapes are uniform.
- **Backward compatible**: existing `/ws/scan` and `/ws/gps` channels untouched; `ConnectionManager` already supports multi-channel (dict channel → clients), no change needed to it.
- Enable the FE to subscribe once and drive the Mission Detail UI (progress bar, live log, map updates, toasts).

---

## 2. Backend Tasks

1. [ ] Create `backend/app/api/routers/ws_mission.py` — `/ws/mission` endpoint + `broadcast_mission_event` helper.
2. [ ] Register router in `app/main.py` (`app.include_router(ws_mission.router)`).
3. [ ] Update Phase-6 executor `_broadcast` to call `broadcast_mission_event` (single source of truth for payloads).
4. [ ] Define event type constants + payload builders in `ws_mission.py` (or `app/core/mission_events.py`).
5. [ ] Emit `mission_skipped` from executor when a scan fails (non-fatal skip, Phase 6 §5.4).
6. [ ] Verify existing `ws_scan.py` / `ws_gps.py` remain untouched.
7. [ ] Write unit + integration tests (TestClient websocket).
8. [ ] Run full test suite (no regressions).

---

## 3. File Changes

### New files
| Path | Description |
|------|-------------|
| `backend/app/api/routers/ws_mission.py` | `/ws/mission` socket + `broadcast_mission_event` + event payload builders |

### Modified files
| Path | Description |
|------|-------------|
| `backend/app/main.py` | Include `ws_mission` router |
| `backend/app/core/mission_executor.py` | Replace ad-hoc `_broadcast` with `broadcast_mission_event` calls |
| `backend/app/api/routers/__init__.py` | Import `ws_mission` (match existing style) |
| `backend/tests/` | `tests/test_ws_mission.py` |

---

## 4. API Specs

### 4.1 `WS /ws/mission`

Standard WebSocket upgrade; no query params. On connect, the client joins the `mission` channel and immediately receives server-push events for any running mission.

**Server→client payload envelope (mirrors existing channels):**
```json
{
  "type": "<event_type>",
  "mission_id": 3,
  "data": { ... }
}
```

> `mission_id` is **top-level** (never duplicated inside `data`) — set by `broadcast_mission_event` (5.1).

### 4.2 Event catalog

#### `mission_started`
```json
{
  "type": "mission_started",
  "mission_id": 3,
  "data": {
    "name": "Jakarta Utara Sweep",
    "status": "RUNNING",
    "total_locations": 10,
    "started_at": "2026-07-31T09:00:06Z"
  }
}
```

#### `mission_progress` — emitted on every GPS poll while RUNNING
```json
{
  "type": "mission_progress",
  "mission_id": 3,
  "data": {
    "current_location_id": 45,
    "visited_locations": 3,
    "total_locations": 10,
    "status": "RUNNING",
    "distance_to_target_meters": 15.2
  }
}
```

#### `mission_visit`
```json
{
  "type": "mission_visit",
  "mission_id": 3,
  "data": {
    "location_id": 45,
    "tower_id": "TWR-005",
    "tower_name": "Jakarta Pusat",
    "scan_session_id": 456,
    "distance_m": 14.2
  }
}
```

#### `mission_skipped` — scan failed (non-fatal) or user skip
```json
{
  "type": "mission_skipped",
  "mission_id": 3,
  "data": {
    "location_id": 45,
    "tower_id": "TWR-005",
    "reason": "SCAN_ERROR"
  }
}
```

#### `mission_paused` / `mission_resumed`
```json
{
  "type": "mission_paused",
  "mission_id": 3,
  "data": { "status": "PAUSED" }
}
```

#### `mission_stopped`
```json
{
  "type": "mission_stopped",
  "mission_id": 3,
  "data": { "status": "STOPPED", "stopped_at": "2026-07-31T09:20:00Z" }
}
```

#### `mission_completed`
```json
{
  "type": "mission_completed",
  "mission_id": 3,
  "data": {
    "status": "COMPLETED",
    "visited_locations": 10,
    "completed_at": "2026-07-31T09:35:00Z"
  }
}
```

#### `mission_failed`
```json
{
  "type": "mission_failed",
  "mission_id": 3,
  "data": {
    "status": "FAILED",
    "reason": "GPS unavailable after 10 consecutive failures"
  }
}
```

> `mission_id` is top-level in every event; `status` is included in `data` for client-side state machines.

---

## 5. Business Logic Specs

### 5.1 `ws_mission.py`

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

MISSION_CHANNEL = "mission"

@router.websocket("/ws/mission")
async def mission_websocket(websocket: WebSocket):
    await manager.connect(websocket, MISSION_CHANNEL)
    try:
        while True:
            if manager.get_connections_count(MISSION_CHANNEL) == 0:
                break
            data = await websocket.receive_text()
            logger.info(f"Received on mission channel: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, MISSION_CHANNEL)
    except Exception as e:
        logger.error(f"Mission WebSocket error: {e}")
        manager.disconnect(websocket, MISSION_CHANNEL)


async def broadcast_mission_event(event_type: str, mission_id: int, **data) -> None:
    await manager.broadcast(
        MISSION_CHANNEL,
        {
            "type": event_type,
            "mission_id": mission_id,
            "data": data,
        },
    )
```

The endpoint loop mirrors `ws_scan.py` (receive-driven keepalive; server push happens via `broadcast`). Client messages are logged and ignored.

### 5.2 Executor integration

Replace Phase-6 `_broadcast` internals with the shared helper:

```python
# mission_executor.py
from app.api.routers.ws_mission import broadcast_mission_event

async def _emit(self, event_type, mission_id, **data):
    try:
        await broadcast_mission_event(event_type, mission_id, **data)
    except Exception:
        logger.exception("Mission WS broadcast failed")   # never break the loop
```

Executor emit points (map from Phase 6):
| Phase-6 location | Event |
|------------------|-------|
| `start` success | `mission_started` (name, total_locations, started_at) |
| loop each GPS poll | `mission_progress` (current_location_id, visited/total, distance_to_target_meters) |
| `_visit` success | `mission_visit` (location_id, tower_id, tower_name, scan_session_id, distance_m) |
| scan failure → skip | `mission_skipped` (reason=`SCAN_ERROR`) |
| `pause` | `mission_paused` |
| `resume` | `mission_resumed` |
| `stop` | `mission_stopped` (stopped_at) |
| all visited | `mission_completed` (visited_locations, completed_at) |
| fatal error | `mission_failed` (reason) |

### 5.3 ConnectionManager — no changes required

The existing `ConnectionManager` (`app/core/websocket_manager.py`) already:
- supports arbitrary channels via `Dict[str, List[WebSocket]]`,
- has `broadcast(channel, data)`, `connect`, `disconnect`, `get_connections_count`.

`broadcast` is fire-and-forget per client (swallows per-client errors, prunes dead sockets). No modification needed for multi-channel.

### 5.4 Backward compatibility

- `/ws/scan` (SCAN_CHANNEL) — untouched.
- `/ws/gps` (GPS_CHANNEL) — untouched.
- A mission-triggered scan still produces `scan_result` on the `scan` channel via the existing scan flow (out of scope here; the executor uses `ScanService` directly, and its results appear under the mission events, not `/ws/scan`).

---

## 6. Acceptance Criteria

### 6.1 Unit tests

| # | Test | Expectation |
|---|------|-------------|
| U01 | `broadcast_mission_event` payload envelope | `{"type", "mission_id" (top-level), "data"}` correct for each event type; `mission_id` not duplicated inside `data` |
| U02 | `mission_progress` data fields | All 5 `data` fields present with right types + top-level `mission_id` |
| U03 | `mission_visit` data fields | tower_id/tower_name/scan_session_id/distance_m present |
| U04 | `mission_failed` reason | Passed through unchanged |
| U05 | Broadcast to mission channel | Only mission subscribers receive; scan/gps subscribers unaffected |
| U06 | Broadcast with 0 subscribers | No error (no-op) |
| U07 | `ConnectionManager` multi-channel | connect/disconnect/count independent per channel |
| U08 | Executor emit on scan failure | Emits `mission_skipped` reason=`SCAN_ERROR`, loop continues |

### 6.2 End-to-end / integration tests

| # | Test | Expectation |
|---|------|-------------|
| E01 | TestClient WS connect `/ws/mission` | Accepted; joins mission channel |
| E02 | Run mission (mock GPS) with subscriber connected | Receives `mission_started` → ≥1 `mission_progress` → `mission_visit`×N → `mission_completed` in order |
| E03 | Pause/resume/stop via HTTP | Subscriber receives matching events |
| E04 | `/ws/scan` and `/ws/gps` still connect | Unchanged behavior (regression) |
| E05 | Disconnect subscriber mid-mission | Broadcast prunes dead socket; server keeps running |
| E06 | Full `pytest` suite | All existing tests still pass (no regressions) |

### 6.3 Verification commands

```bash
cd ~/Cellular-Discovery-Service/backend

# Automated (primary path)
.venv/bin/pytest -q tests/test_ws_mission.py

# Manual: run with mock GPS, then connect with a websocket client
.venv/bin/python - <<'PY'
import asyncio, json, websockets

async def main():
    async with websockets.connect("ws://localhost:8000/ws/mission") as ws:
        # Trigger: POST /api/v1/missions/1/start from another shell
        for _ in range(20):
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                print(msg["type"], msg.get("data", {}).get("status", ""))
            except asyncio.TimeoutError:
                continue

asyncio.run(main())
PY
```

---

### Checklist

- [ ] `/ws/mission` endpoint registered in `app/main.py`
- [ ] `broadcast_mission_event` helper (single payload source)
- [ ] Executor emits all 9 event types at the right points
- [ ] `mission_skipped` on scan failure
- [ ] `ConnectionManager` unchanged
- [ ] `/ws/scan`, `/ws/gps` untouched
- [ ] All Acceptance Criteria (U01–U08, E01–E06) pass
