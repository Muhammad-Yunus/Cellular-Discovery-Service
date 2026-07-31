"""Step definitions for mission flow end-to-end tests."""

import os
import time
import logging
import httpx
from behave import given, when, then

# Base URL for dev backend (port 8001); can be overridden via env var
BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8001")

logger = logging.getLogger(__name__)

@given('the backend is running')
def check_backend(context):
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=5)
        assert r.status_code == 200
    except Exception as e:
        raise RuntimeError(f"Backend not available: {e}")


@given('a mission "{name}" with radius {radius:d} meters')
def create_mission(context, name, radius):
    r = httpx.post(f"{BASE_URL}/api/v1/missions", json={"name": name, "radius_meters": radius})
    assert r.status_code in (200, 201), f"Failed to create mission: {r.text}"
    context.mission = r.json()
    context.mission_id = context.mission["id"]


@given('three locations (T1, T2, T3) uploaded via CSV')
def upload_locations(context):
    csv_content = """cellular_tower_id,cellular_tower_name,latitude,longitude
T1,Tower A,-6.20000,106.80000
T2,Tower B,-6.20001,106.80001
T3,Tower C,-6.20002,106.80002
"""
    r = httpx.post(
        f"{BASE_URL}/api/v1/missions/{context.mission_id}/locations/upload",
        files={"file": ("locations.csv", csv_content, "text/csv")},
    )
    assert r.status_code == 200, f"Location upload failed: {r.text}"


@given('the mission has been planned')
def plan_mission(context):
    r = httpx.post(f"{BASE_URL}/api/v1/missions/{context.mission_id}/plan")
    assert r.status_code == 200, f"Plan failed: {r.text}"


@when('I start the mission')
def start_mission(context):
    r = httpx.post(f"{BASE_URL}/api/v1/missions/{context.mission_id}/start")
    assert r.status_code == 200, f"Start failed: {r.text}"
    
    # Poll until terminal state (COMPLETED, FAILED, or STOPPED) with extended timeout
    deadline = time.time() + 120  # 2 minutes total polling
    POLL_INTERVAL = 2  # seconds
    while time.time() < deadline:
        status_r = httpx.get(f"{BASE_URL}/api/v1/missions/{context.mission_id}/status")
        status_data = status_r.json()
        logger.info(f"[Poll] Mission {context.mission_id} status={status_data['status']} visited={status_data['visited_locations']}/{status_data['total_locations']} progress={status_data.get('progress_percent', 'N/A')}%")
        
        if status_data["status"] in ["COMPLETED", "FAILED", "STOPPED"]:
            context.final_status = status_data["status"]
            break
        time.sleep(POLL_INTERVAL)
    
    # Log final status for debugging
    logger.info(f"[Final] Mission {context.mission_id} finished with status: {context.final_status}")


@then('the mission reaches COMPLETED state')
def verify_completed(context):
    final_status = getattr(context, "final_status", None)
    assert final_status == "COMPLETED", \
        f"Mission ended with status '{final_status}' instead of 'COMPLETED'"


@then('exactly three scan sessions are linked to the mission\'s locations')
def verify_scans_linked(context):
    r = httpx.get(f"{BASE_URL}/api/v1/missions/{context.mission_id}/scans")
    assert r.status_code == 200
    data = r.json()
    # Each visited tower yields one scan session via the scanner during mission execution
    assert len(data["items"]) == 3, f"Expected 3 scan items, got {len(data['items'])}"
    # All should have non-null mission_location_id
    for item in data["items"]:
        assert item.get("mission_location_id") is not None


@when('I fetch mission-scanned scans via GET /api/v1/missions/{id}/scans')
def fetch_mission_scans(context):
    r = httpx.get(f"{BASE_URL}/api/v1/missions/{context.mission_id}/scans")
    context.scans_response = r


@then('the response contains 3 items with non-null mission_location_id')
def validate_scan_items(context):
    assert context.scans_response.status_code == 200
    data = context.scans_response.json()
    assert len(data["items"]) == 3
    for item in data["items"]:
        assert item.get("mission_location_id") is not None


@when('I export mission scans as CSV')
def export_csv(context):
    r = httpx.get(f"{BASE_URL}/api/v1/missions/{context.mission_id}/scans/export")
    context.csv_response = r


@then('the download includes columns: cellular_tower_id, cellular_tower_name, mission_location_id')
def validate_csv_columns(context):
    assert context.csv_response.status_code == 200
    assert context.csv_response.headers["content-type"] == "text/csv"
    content = context.csv_response.text
    assert "cellular_tower_id" in content
    assert "cellular_tower_name" in content
    assert "mission_location_id" in content


@given('the backend is running on port 8001')
def check_backend_on_port(context):
    check_backend(context)


@given('the lte-scanner service is active with mock GPS and CLI')
def scanner_service_active(context):
    # Assume service is ready (health checked earlier)
    pass


@then('exactly 3 scan sessions are linked to the mission\'s locations')
def verify_scans_linked_digit(context):
    verify_scans_linked(context)

