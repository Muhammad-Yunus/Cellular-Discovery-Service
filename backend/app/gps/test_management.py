"""Test-only management endpoints.

This module is ONLY imported and mounted when the environment variable
``TEST_MANAGEMENT_ENDPOINTS=1`` is set at process start. In production the
import is skipped entirely, so these endpoints do not exist.

Endpoints
---------
GET  /test/gps/mock/fail                — return current GPS fault injection state
PUT  /test/gps/mock/fail                — toggle GPS fault injection on/off
GET  /test/missions                     — list all test-prefixed missions (for cleanup)
POST /test/missions/cleanup             — bulk force-stop + delete all test missions
DELETE /test/missions/{mission_id}      — force-delete a single mission (bypasses status check)
POST /test/missions/{mission_id}/force-stop
                                        — force-stop a mission, ignoring status guards

All "bulk" operations only touch missions whose name matches
``TEST_NAME_PREFIXES`` — these prefixes are defined in the e2e_test
environment.py and never match production mission names.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Iterable

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/test", tags=["test-management"])


# ---------------------------------------------------------------------------
# GPS fault injection state
# ---------------------------------------------------------------------------

# Mutable state shared between requests — safe for single-process test runner.
_gps_fail_state = bool(os.environ.get("MOCK_GPS_FAIL") == "1")


@asynccontextmanager
async def _gps_manager(_):
    yield


@router.get("/gps/mock/fail")
def get_mock_gps_fail_state():
    """Return current GPS fault-injection state."""
    return {"fail": _gps_fail_state}


@router.put("/gps/mock/fail")
def set_mock_gps_fail_state(payload: dict):
    """Toggle GPS fault simulation on/off.

    payload: ``{"fail": true}``  — enable
    payload: ``{"fail": false}`` — disable
    """
    global _gps_fail_state
    fail = bool(payload.get("fail", False))
    _gps_fail_state = fail
    os.environ["MOCK_GPS_FAIL"] = "1" if fail else "0"
    # Also update the MockGPSProvider's global state, if available.
    try:
        from app.gps.mock_provider import _set_test_fail_state  # type: ignore

        _set_test_fail_state(fail)
    except Exception:
        # Module not present or import failed — silently ignore. The mock GPS
        # provider may not have a hook for live fault injection in every
        # version, but the global flag and env var are still updated so other
        # paths (e.g. startup checks) can react.
        pass
    return {"fail": _gps_fail_state}


# ---------------------------------------------------------------------------
# CLI fault injection state
# ---------------------------------------------------------------------------

_cli_fail_state: bool = bool(os.environ.get("MOCK_CLI_FAIL"))
# Counter for fail-N-times mode (S06 scan failure handling).
# When >0, CLI adapter will raise CLIError and decrement; when it reaches 0,
# fault injection stops automatically.
_cli_fail_remaining: int = 0


def _decrement_cli_fail() -> bool:
    """Decrement the fail counter. Returns True if a fail should still occur.

    Called by CLIAdapter.execute() before raising CLIError. If the counter
    is already 0 (or was never set), this is a no-op and the caller continues
    normally — but the standard call path checks the env var, so this only
    matters when MOCK_CLI_FAIL is already set.
    """
    global _cli_fail_remaining
    if _cli_fail_remaining > 0:
        _cli_fail_remaining -= 1
        if _cli_fail_remaining <= 0:
            os.environ["MOCK_CLI_FAIL"] = ""
            _cli_fail_state = False
        return True
    return False


@router.get("/cli/mock/fail")
def get_mock_cli_fail_state():
    """Return current CLI fault-injection state."""
    return {"fail": bool(_cli_fail_state), "remaining": _cli_fail_remaining}


@router.put("/cli/mock/fail")
def set_mock_cli_fail_state(payload: dict):
    """Toggle CLI fault simulation on/off.

    payload: ``{"fail": true}``                  — enable (fail forever)
    payload: ``{"fail": false}``                 — disable
    payload: ``{"fail": true, "remaining": N}``   — fail next N times then auto-disable
    payload: ``{"remaining": 0}``                 — disable
    """
    global _cli_fail_state, _cli_fail_remaining
    fail = bool(payload.get("fail", False))
    remaining = int(payload.get("remaining", -1))

    if fail and remaining > 0:
        # Fail-once / fail-N-times mode
        _cli_fail_state = True
        _cli_fail_remaining = remaining
        os.environ["MOCK_CLI_FAIL"] = "1"
    elif fail:
        # Fail-forever mode (default when fail=True and no remaining given)
        _cli_fail_state = True
        _cli_fail_remaining = 0
        os.environ["MOCK_CLI_FAIL"] = "1"
    else:
        # Disable
        _cli_fail_state = False
        _cli_fail_remaining = 0
        os.environ["MOCK_CLI_FAIL"] = ""
    return {"fail": _cli_fail_state, "remaining": _cli_fail_remaining}


# ---------------------------------------------------------------------------
# Mission bulk cleanup endpoints
# ---------------------------------------------------------------------------

# Must stay in sync with e2e_test/features/environment.py::TEST_NAME_PREFIXES
TEST_NAME_PREFIXES: tuple[str, ...] = (
    "concurrent-",
    "field-mission",
    "test-",
    "mission-",
    "e2e-",
    "s06-",  # ADD: test mission S06 scan failure handling
)


def _is_test_mission(name: str) -> bool:
    return isinstance(name, str) and any(
        name.startswith(prefix) for prefix in TEST_NAME_PREFIXES
    )


def _get_session() -> Session:
    """Return a new SQLAlchemy session bound to the app's engine.

    Imported lazily to avoid circular imports at module load.
    """
    from app.db.session import SessionLocal  # type: ignore

    return SessionLocal()


def _force_stop_mission(db: Session, mission_id: int) -> dict:
    """Best-effort: stop a mission regardless of its current status.

    Returns a small status dict describing what happened.
    """
    from app.db.models.mission import Mission  # type: ignore

    mission: Mission | None = (
        db.query(Mission).filter(Mission.id == mission_id).first()
    )
    if mission is None:
        return {"id": mission_id, "result": "not_found"}

    # Already terminal — no-op.
    if mission.status in {"STOPPED", "COMPLETED", "FAILED"}:
        return {"id": mission_id, "result": "already_terminal", "status": mission.status}

    from datetime import datetime, timezone  # local import keeps top clean

    mission.status = "STOPPED"
    mission.stopped_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": mission_id, "result": "force_stopped", "status": "STOPPED"}


def _force_delete_mission(db: Session, mission_id: int) -> dict:
    """Best-effort: delete a mission regardless of status.

    Returns ``{"id": mission_id, "result": "deleted"}`` on success.
    """
    from app.db.models.mission import Mission  # type: ignore

    mission: Mission | None = (
        db.query(Mission).filter(Mission.id == mission_id).first()
    )
    if mission is None:
        return {"id": mission_id, "result": "not_found"}
    db.delete(mission)
    db.commit()
    return {"id": mission_id, "result": "deleted", "name": mission.name}


@router.get("/missions")
def list_test_missions():
    """Return all missions whose name starts with one of TEST_NAME_PREFIXES.

    These are the only missions bulk endpoints will ever touch. Production
    missions (no matching prefix) are not returned.
    """
    from app.db.models.mission import Mission  # type: ignore

    db = _get_session()
    try:
        all_missions = db.query(Mission).all()
        items = [
            {
                "id": m.id,
                "name": m.name,
                "status": m.status,
                "total_locations": m.total_locations,
                "visited_locations": m.visited_locations,
            }
            for m in all_missions
            if _is_test_mission(m.name or "")
        ]
        return {"items": items, "total": len(items)}
    finally:
        db.close()


@router.post("/missions/cleanup")
def bulk_cleanup_test_missions():
    """Force-stop then delete every mission whose name starts with a test prefix.

    Idempotent and safe — only touches names that begin with one of
    TEST_NAME_PREFIXES. Returns a summary of what was stopped and deleted.
    """
    from app.db.models.mission import Mission  # type: ignore

    db = _get_session()
    stopped: list[int] = []
    deleted: list[int] = []
    skipped: list[int] = []
    try:
        all_missions = db.query(Mission).all()
        targets: Iterable = [m for m in all_missions if _is_test_mission(m.name or "")]

        for m in list(targets):
            mid = m.id
            # Step 1: force-stop if active.
            stop_info = _force_stop_mission(db, mid)
            if stop_info["result"] == "force_stopped":
                stopped.append(mid)

        # Refresh and delete (force-stop may have changed status).
        for mid in [m.id for m in targets]:
            try:
                del_info = _force_delete_mission(db, mid)
                if del_info["result"] == "deleted":
                    deleted.append(mid)
                else:
                    skipped.append(mid)
            except Exception as exc:  # noqa: BLE001
                skipped.append(mid)
                # Roll back this transaction so subsequent deletes still work.
                db.rollback()
                # Log via stderr — there's no logger configured here, but
                # stdout/stderr is captured by behave/pytest if needed.
                import sys

                print(
                    f"[test_management] cleanup failed for mission {mid}: {exc}",
                    file=sys.stderr,
                )
        return {
            "stopped": stopped,
            "deleted": deleted,
            "skipped": skipped,
            "total_processed": len(stopped) + len(deleted),
        }
    finally:
        db.close()


@router.delete("/missions/{mission_id}")
def force_delete_one_mission(mission_id: int):
    """Force-delete a single mission, bypassing the ``_ensure_inactive`` guard.

    Useful for the SafetyNet cleanup when a mission is stuck in
    STARTING/RUNNING/PAUSED. Only deletes if the mission name matches one of
    TEST_NAME_PREFIXES.
    """
    from app.db.models.mission import Mission  # type: ignore

    db = _get_session()
    try:
        mission = db.query(Mission).filter(Mission.id == mission_id).first()
        if mission is None:
            raise HTTPException(status_code=404, detail="Mission not found")
        if not _is_test_mission(mission.name or ""):
            raise HTTPException(
                status_code=403,
                detail="Refusing to delete non-test mission",
            )
        # Force-stop first so we never leave the executor in a weird state.
        _force_stop_mission(db, mission_id)
        db.delete(mission)
        db.commit()
        return {"id": mission_id, "result": "deleted"}
    finally:
        db.close()


@router.post("/missions/{mission_id}/force-stop")
def force_stop_one_mission(mission_id: int):
    """Force-stop a single mission, ignoring the status guard."""
    db = _get_session()
    try:
        return _force_stop_mission(db, mission_id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Activation — only attach when the env var is explicitly set.
# ---------------------------------------------------------------------------

if os.environ.get("TEST_MANAGEMENT_ENDPOINTS") == "1":
    # Import here to avoid circular imports in production.
    from fastapi import FastAPI  # noqa: E402

    def attach(app: FastAPI):
        """Attach test-only management endpoints to the FastAPI app."""
        app.include_router(router, prefix="")
        # Add the manager so lifespan events fire.
        app.router.lifespan_context = _gps_manager