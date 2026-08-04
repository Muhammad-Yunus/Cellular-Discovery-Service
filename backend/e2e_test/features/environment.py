"""Behave conftest for e2e tests."""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8001"

# Must stay in sync with app.gps.test_management.TEST_NAME_PREFIXES
TEST_NAME_PREFIXES = (
    "concurrent-",
    "field-mission",
    "test-",
    "mission-",
    "e2e-",
    "s06-",  # ADD: test mission S06 scan failure handling
    "route-",  # ADD: test mission S07 route management
    "skip-",  # ADD: test mission S08 skip location
)


def before_all(context):
    """Start any shared resources."""
    context.base_url = BASE_URL
    context.client = httpx.Client(base_url=BASE_URL, timeout=10.0)


def before_scenario(context, scenario):
    """Safety net: aggressively clean up ALL test missions from any prior run.

    This prevents stale concurrent-a/b missions from blocking the current
    scenario (e.g. a COMPLETED or FAILED mission left behind by a previous
    assertion failure would still count toward the "one-running-mission" guard).
    """
    context.step_count = getattr(context, "step_count", 0) + 1
    try:
        # Use bulk cleanup endpoint if available (faster, single HTTP call).
        r = httpx.post(f"{BASE_URL}/test/missions/cleanup", timeout=30.0, verify=False)
        if r.status_code == 200:
            result = r.json()
            logger.info(
                f"[SafetyNet] bulk cleanup: stopped={result.get('stopped')}, "
                f"deleted={result.get('deleted')}, "
                f"skipped={result.get('skipped')}"
            )
        else:
            if r.status_code == 404:
                logger.warning(
                    "[SafetyNet] /test/missions/cleanup 404 — "
                    "TEST_MANAGEMENT_ENDPOINTS not active"
                )
            else:
                logger.warning(
                    f"[SafetyNet] /test/missions/cleanup returned {r.status_code}: "
                    f"{r.text[:200]}"
                )
            # Fallback: iterate and delete individually (server may not have test endpoints).
            r = httpx.get(f"{BASE_URL}/api/v1/missions?page_size=100", timeout=5, verify=False)
            if r.status_code == 200:
                for m in r.json().get("items", []):
                    name = m.get("name", "")
                    if any(name.startswith(p) for p in TEST_NAME_PREFIXES):
                        mid = m["id"]
                        status = m.get("status", "")
                        if status in ("STARTING", "RUNNING", "PAUSED"):
                            try:
                                httpx.post(f"{BASE_URL}/api/v1/missions/{mid}/stop", timeout=5, verify=False)
                            except Exception:
                                pass
                        try:
                            httpx.delete(f"{BASE_URL}/api/v1/missions/{mid}", timeout=5, verify=False)
                        except Exception:
                            pass
    except Exception as e:
        logger.warning(f"[SafetyNet] Pre-scenario cleanup: {e}")


def after_all(context):
    """Cleanup."""
    context.client.close()


def background(context):
    """Ensure backend is alive - run as part of scenario."""
    try:
        r = context.client.get("/health", timeout=5, verify=False)
        assert r.status_code == 200
    except Exception as e:
        raise RuntimeError(f"Backend not healthy: {e}")


def _is_test_mission(name: str) -> bool:
    return isinstance(name, str) and any(name.startswith(p) for p in TEST_NAME_PREFIXES)


def _force_stop(mission_id: int) -> None:
    """Best-effort stop a mission so it can be deleted."""
    try:
        httpx.post(f"{BASE_URL}/test/missions/{mission_id}/force-stop", timeout=5, verify=False)
    except Exception:
        # Fallback to standard stop endpoint.
        try:
            httpx.post(f"{BASE_URL}/api/v1/missions/{mission_id}/stop", timeout=5, verify=False)
        except Exception as e:
            logger.warning(f"[SafetyNet] Pre-stop failed: {e}")


def _safe_delete(mission_id: int, name: str, retries: int = 3) -> None:
    """Best-effort delete with retries — mission may be starting up."""
    for i in range(retries):
        try:
            # Try the force-delete endpoint first.
            r = httpx.delete(f"{BASE_URL}/test/missions/{mission_id}", timeout=5, verify=False)
            if r.status_code == 200:
                logger.info(f"[SafetyNet] Deleted mission {mission_id} ({name})")
                return
            if r.status_code == 404:
                logger.info(f"[SafetyNet] Mission {mission_id} already gone")
                return
            # If non-404, wait a bit and retry (mission may be transitioning).
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"[SafetyNet] DELETE attempt {i+1} failed for mission {mission_id}: {e}")
            time.sleep(0.5)
    # Final fallback.
    try:
        httpx.delete(f"{BASE_URL}/api/v1/missions/{mission_id}", timeout=10, verify=False)
    except Exception as e:
        logger.warning(f"[SafetyNet] Final DELETE failed for {mission_id}: {e}")


def after_scenario(context, scenario):
    """Safety net: clean up any test-owned missions left behind by a failing scenario.

    Runs AFTER each scenario, regardless of pass/fail. Honors explicit cleanup done in
    the steps (we already-popped names are skipped). Only touches missions whose name
    matches TEST_NAME_PREFIXES to avoid touching user data / history missions.
    Also resets GPS fault injection if it was enabled.
    """
    # Reset GPS fault injection if it was active.
    try:
        httpx.put(
            f"{BASE_URL}/test/gps/mock/fail",
            json={"fail": False},
            timeout=5,
            verify=False,
        )
    except Exception:
        pass

    # Reset CLI fault injection if it was active.
    try:
        httpx.put(
            f"{BASE_URL}/test/cli/mock/fail",
            json={"fail": False},
            timeout=5,
            verify=False,
        )
    except Exception:
        pass

    missions = getattr(context, "missions", None)
    if not missions:
        return

    for name in list(missions.keys()):
        mission = missions.get(name) or {}
        mission_id = mission.get("id")
        if mission_id is None:
            continue
        if not _is_test_mission(name):
            logger.info(f"[SafetyNet] Skipping non-test mission '{name}' (id={mission_id})")
            continue
        _force_stop(mission_id)
        _safe_delete(mission_id, name)
        missions.pop(name, None)
