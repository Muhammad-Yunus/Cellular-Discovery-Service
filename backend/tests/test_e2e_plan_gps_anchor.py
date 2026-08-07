"""End-to-end test: /missions/{id}/plan uses GPS-anchored start selection.

Verifies three scenarios:
  1. No GPS fix available from provider                  -> 503/400
  2. GPS fix provided                                     -> plan succeeds,
     sequence_order=1 is the tower closest to the GPS fix.
  3. Explicit start_location_id still wins                -> plan succeeds,
     sequence_order=1 matches the manual override even when it is *not*
     the geographically closest tower.

The live GPS provider is replaced by a FakeGPS whose coordinates are
swapped between scenarios via app.dependency_overrides.
"""
import sys
from io import StringIO

from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies.providers import get_gps_provider
from app.db.database import SessionLocal
from app.db.models import Mission, MissionLocation, ScanSession
from app.gps.exceptions import GPSError
from app.gps.schemas import GPSLocation
from app.repositories.mission_repository import MissionRepository


def _wipe():
    with SessionLocal() as db:
        db.query(MissionLocation).delete()
        db.query(ScanSession).delete()
        db.query(Mission).delete()
        db.commit()


def _create_mission(client, name="GPS-PLAN-E2E"):
    r = client.post("/api/v1/missions", json={
        "name": name, "description": "gps anchor test"
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload_far_from_gps(client, mid):
    """Five towers clustered in the Papua region. The fake GPS will be
    placed close to TWR-A so the anchor test is unambiguous.
    """
    rows = [
        ("TWR-A", "A", -2.5, 140.0),
        ("TWR-B", "B", -2.7, 140.2),
        ("TWR-C", "C", -2.9, 140.4),
        ("TWR-D", "D", -3.1, 140.6),
        ("TWR-E", "E", -3.3, 140.8),
    ]
    buf = StringIO()
    buf.write("cellular_tower_id,cellular_tower_name,latitude,longitude\n")
    for t, name, lat, lon in rows:
        buf.write(f"{t},{name},{lat},{lon}\n")
    files = {"file": ("locations.csv", buf.getvalue(), "text/csv")}
    r = client.post(
        f"/api/v1/missions/{mid}/locations/upload", files=files
    )
    assert r.status_code == 200, r.text


class _StubGPS:
    """A GPS provider stub whose coordinates can be swapped per scenario."""

    def __init__(self, lat=None, lon=None, fail=False):
        self.lat = lat
        self.lon = lon
        self.fail = fail

    def get_location(self):
        if self.fail:
            raise GPSError("No GPS fix. Fix quality: 0")
        return GPSLocation(latitude=self.lat, longitude=self.lon)

    def is_available(self):
        return True


def _locations_in_order(client, mid):
    r = client.get(f"/api/v1/missions/{mid}/route")
    return r.json()["items"]


def main():
    client = TestClient(app)

    print("=" * 72)
    print("END-TO-END TEST: /plan GPS-anchored start selection")
    print("=" * 72)

    # ---------- Scenario 1: GPS provider returns no fix ----------
    _wipe()
    mid = _create_mission(client, name="NO-GPS")
    _upload_far_from_gps(client, mid)
    app.dependency_overrides[get_gps_provider] = lambda: _StubGPS(fail=True)
    r = client.post(f"/api/v1/missions/{mid}/plan")
    print("\n[Scenario 1] /plan with no GPS fix")
    print(f"  status={r.status_code}  body={r.json()}")
    assert r.status_code in (400, 503), r.text
    assert "fix" in r.json().get("detail", "").lower() or "gps" in r.json().get("detail", "").lower()
    print("  -> plan correctly rejected with no GPS fix")

    # ---------- Scenario 2: GPS fix near TWR-A ----------
    _wipe()
    mid = _create_mission(client, name="WITH-GPS")
    _upload_far_from_gps(client, mid)
    app.dependency_overrides[get_gps_provider] = lambda: _StubGPS(
        lat=-2.55, lon=140.02
    )
    r = client.post(f"/api/v1/missions/{mid}/plan")
    print(f"\n[Scenario 2] /plan with GPS anchor (-2.55, 140.02)")
    print(f"  status={r.status_code}")
    assert r.status_code == 200, r.text
    items = _locations_in_order(client, mid)
    first = items[0]
    print(f"  sequence_order=1 -> tower={first['cellular_tower_id']}")
    assert first["sequence_order"] == 1
    assert first["cellular_tower_id"] == "TWR-A", \
        f"expected TWR-A (closest to GPS), got {first['cellular_tower_id']}"
    print("  -> TWR-A correctly selected as starting tower (closest to GPS)")

    # Confirm mission.start_location_id was persisted
    with SessionLocal() as db:
        m = MissionRepository(db).get_by_id(mid)
        assert m.start_location_id is not None
        loc = db.query(MissionLocation).filter(
            MissionLocation.id == m.start_location_id
        ).first()
        assert loc.cellular_tower_id == "TWR-A"
    print(f"  -> mission.start_location_id persisted (={m.start_location_id})")

    # ---------- Scenario 3: manual start_location_id wins ----------
    _wipe()
    mid = _create_mission(client, name="MANUAL-OVERRIDE")
    _upload_far_from_gps(client, mid)
    app.dependency_overrides[get_gps_provider] = lambda: _StubGPS(
        lat=-2.55, lon=140.02
    )
    # Force TWR-C as manual start even though TWR-A is closer to GPS.
    with SessionLocal() as db:
        m = db.query(Mission).filter(Mission.id == mid).first()
        c_loc = db.query(MissionLocation).filter(
            MissionLocation.mission_id == mid,
            MissionLocation.cellular_tower_id == "TWR-C"
        ).first()
        m.start_location_id = c_loc.id
        db.commit()

    r = client.post(f"/api/v1/missions/{mid}/plan")
    print(f"\n[Scenario 3] /plan with manual start_location_id (TWR-C)")
    print(f"  status={r.status_code}")
    assert r.status_code == 200, r.text
    items = _locations_in_order(client, mid)
    first = items[0]
    print(f"  sequence_order=1 -> tower={first['cellular_tower_id']}")
    assert first["sequence_order"] == 1
    assert first["cellular_tower_id"] == "TWR-C", \
        f"manual override ignored: got {first['cellular_tower_id']}"
    print("  -> manual override respected, GPS anchor bypassed")

    # ---------- Scenario 4 (linjer-tower case from bug report) ----------
    # Five towers aligned north-to-south at 1km spacing, device 2km east
    # of the middle one. Without GPS anchoring, the NN+2opt would still
    # produce a reasonable route. With GPS anchoring, the route should
    # be optimal (shortest total path). The device is at (-6.282,
    # 106.818), so:
    #   * Nearest tower is TWR-3 (~2 km east)
    #   * NN picks TWR-3 first, then explores either (3->2->1) or
    #     (3->4->5). 2-opt then picks the shorter full tour.
    _wipe()
    mid = _create_mission(client, name="LINJER")
    rows = [
        ("TWR-1", "One",   -6.300, 106.800),
        ("TWR-2", "Two",   -6.291, 106.800),
        ("TWR-3", "Three", -6.282, 106.800),
        ("TWR-4", "Four",  -6.273, 106.800),
        ("TWR-5", "Five",  -6.264, 106.800),
    ]
    buf = StringIO()
    buf.write("cellular_tower_id,cellular_tower_name,latitude,longitude\n")
    for t, name, lat, lon in rows:
        buf.write(f"{t},{name},{lat},{lon}\n")
    files = {"file": ("locations.csv", buf.getvalue(), "text/csv")}
    r = client.post(f"/api/v1/missions/{mid}/locations/upload", files=files)
    assert r.status_code == 200, r.text

    # Device is at the middle tower (TWR-3) plus 2km east.
    app.dependency_overrides[get_gps_provider] = lambda: _StubGPS(
        lat=-6.282, lon=106.818
    )
    r = client.post(f"/api/v1/missions/{mid}/plan")
    assert r.status_code == 200, r.text
    items = _locations_in_order(client, mid)
    tower_ids = [item["cellular_tower_id"] for item in items]
    seq_lats = [item["latitude"] for item in items]
    print(f"\n[Scenario 4] /plan with linear-tower cluster and GPS east of TWR-3")
    print(f"  status={r.status_code}")
    print(f"  route = {tower_ids}")
    # Verify the route is monotonic (no back-tracking). With towers
    # arranged north-to-south at -6.300, -6.291, -6.282, -6.273,
    # -6.264, an optimal route from device (2 km east of TWR-3) goes
    # either 3->4->5 (south) or 3->2->1 (north) and then all the way
    # to the opposite end. 2-opt picks the shorter of the two, which
    # in this case is 3->4->5 (total ~6 km vs 3->2->1 which is ~6 km
    # too but the path ordering is what matters).
    # Check monotonicity from first tower onward.
    monotonic_inc = all(b > a for a, b in zip(seq_lats, seq_lats[1:]))
    monotonic_dec = all(b < a for a, b in zip(seq_lats, seq_lats[1:]))
    assert monotonic_inc or monotonic_dec, \
        f"expected monotonic latitude, got {seq_lats}"
    print(f"  -> monotonic route (no back-tracking): lat={seq_lats}")

    print("\n" + "=" * 72)
    print("ALL SCENARIOS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\nASSERTION FAILED: {e}", file=sys.stderr)
        sys.exit(1)
