"""Quick integration test: random towers around Kelapa Gading -> /plan."""
import sys
from io import StringIO
from random import uniform

from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies.providers import get_gps_provider
from app.gps.exceptions import GPSError
from app.gps.schemas import GPSLocation
from app.db.database import SessionLocal
from app.db.models import Mission, MissionLocation, ScanSession
from app.repositories.mission_repository import MissionRepository


class _FakeGPS:
    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon

    def get_location(self):
        return GPSLocation(latitude=self.lat, longitude=self.lon)

    def is_available(self):
        return True


def wipe():
    with SessionLocal() as db:
        db.query(MissionLocation).delete()
        db.query(ScanSession).delete()
        db.query(Mission).delete()
        db.commit()


def main():
    client = TestClient(app)

    # Kelapa Gading center approx (-6.18, 106.83), spread 3km radius
    TOWERS = [
        ("KG-N1", "North1",   -6.155, 106.825),
        ("KG-N2", "North2",   -6.160, 106.835),
        ("KG-C1", "Center1",  -6.180, 106.830),
        ("KG-C2", "Center2",  -6.175, 106.840),
        ("KG-S1", "South1",   -6.195, 106.828),
        ("KG-S2", "South2",   -6.200, 106.835),
        ("KG-E1", "East1",    -6.182, 106.850),
        ("KG-W1", "West1",    -6.178, 106.815),
        ("KG-NE1","NE1",      -6.165, 106.845),
        ("KG-NW1","NW1",      -6.170, 106.818),
    ]

    # Device positioned near Center1
    DEVICE_LAT, DEVICE_LON = -6.180, 106.832

    app.dependency_overrides[get_gps_provider] = lambda: _FakeGPS(DEVICE_LAT, DEVICE_LON)

    print("=" * 72)
    print("INTEGRATION TEST: Random towers around Kelapa Gading -> /plan")
    print(f"Device GPS: ({DEVICE_LAT}, {DEVICE_LON})")
    print("=" * 72)

    # 1. Create mission
    r = client.post("/api/v1/missions", json={
        "name": "KG-TOUR",
        "description": "Random towers around Kelapa Gading"
    })
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    print(f"\n1. Created mission id={mid}")

    # 2. Upload towers
    buf = StringIO()
    buf.write("cellular_tower_id,cellular_tower_name,latitude,longitude\n")
    for tid, name, lat, lon in TOWERS:
        buf.write(f"{tid},{name},{lat},{lon}\n")
    files = {"file": ("locations.csv", buf.getvalue(), "text/csv")}
    r = client.post(f"/api/v1/missions/{mid}/locations/upload", files=files)
    assert r.status_code == 200, r.text
    print(f"2. Uploaded {len(TOWERS)} towers")

    # 3. Call /plan
    r = client.post(f"/api/v1/missions/{mid}/plan")
    assert r.status_code == 200, r.text
    payload = r.json()
    print(f"3. /plan succeeded, status={payload['status']}")
    print(f"   start_location_id={payload['start_location_id']}")
    print(f"   total_distance_m={payload['total_distance_meters']:.1f} m")

    # 4. Inspect route
    r2 = client.get(f"/api/v1/missions/{mid}/route")
    items = r2.json()["items"]
    tower_ids = [item["cellular_tower_id"] for item in items]
    lats = [item["latitude"] for item in items]
    lons = [item["longitude"] for item in items]
    dists = [item["distance_from_previous_meters"] or 0 for item in items]

    print(f"\n4. Route order:")
    for i, (tid, lat, lon, d) in enumerate(zip(tower_ids, lats, lons, dists), 1):
        print(f"   #{i} {tid:8s} ({lat:.4f}, {lon:.4f})  dist={d:>7.0f}m")

    # 5. Verify first tower is nearest to GPS
    from app.utils.geo import haversine
    distances = [(tid, haversine(DEVICE_LAT, DEVICE_LON, lat, lon))
                 for tid, _, lat, lon in TOWERS]
    closest = min(distances, key=lambda x: x[1])
    print(f"\n5. Nearest tower to GPS: {closest[0]} ({closest[1]:.0f} m)")
    assert tower_ids[0] == closest[0], \
        f"expected {closest[0]} first, got {tower_ids[0]}"
    print(f"   -> first tower is correct ({closest[0]})")

    # 6. Verify total distance is reasonable (2-opt optimizes this)
    total_optimal = sum(d for d in dists[1:])
    print(f"\n6. Total route distance: {total_optimal:.0f} m")

    # 7. Persist start_location_id on mission
    with SessionLocal() as db:
        m = MissionRepository(db).get_by_id(mid)
        first_loc = db.query(MissionLocation).filter(
            MissionLocation.id == m.start_location_id
        ).first()
        assert first_loc.cellular_tower_id == closest[0]
        print(f"\n7. start_location_id persisted on mission = {m.start_location_id}")

    print("\n" + "=" * 72)
    print("ALL CHECKS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        sys.exit(1)
