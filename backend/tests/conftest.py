import time
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings
from app.db.base import Base
from app.db.database import get_db
from app.db.models import Mission
from app.gps.exceptions import GPSError
from app.gps.schemas import GPSLocation
from app.main import app
from app.services import LocationService, MissionPlannerService
from app.services.scan_service import ScanService

import tempfile
import os

# Use a unique temp file per test session to avoid cross-test pollution
TEST_DATABASE_FILE = os.path.join(tempfile.gettempdir(), f"cds_test_{os.getpid()}.db")
TEST_DATABASE_URL = f"sqlite:///{TEST_DATABASE_FILE}"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _strip_schemas():
    for table in Base.metadata.tables.values():
        if hasattr(table, "schema") and table.schema:
            table.schema = None


@pytest.fixture(scope="function")
def db_session():
    _strip_schemas()
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    from fastapi.testclient import TestClient
    import app.core.mission_executor as mission_executor_module
    from app.api.dependencies.providers import get_gps_provider

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fake_gps = FakeGPS()
    app.dependency_overrides[get_gps_provider] = lambda: fake_gps

    original_session_local = mission_executor_module.SessionLocal
    mission_executor_module.SessionLocal = TestingSessionLocal
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        mission_executor_module.SessionLocal = original_session_local


CSV_HEADER = "cellular_tower_id,cellular_tower_name,latitude,longitude\n"
CSV_1 = CSV_HEADER + "T1,A,-6.200,106.800\n"
CSV_5 = (
    CSV_HEADER
    + "T1,A,-6.200,106.800\n"
    + "T2,B,-6.260,106.820\n"
    + "T3,C,-6.150,106.780\n"
    + "T4,D,-6.220,106.860\n"
    + "T5,E,-6.280,106.830\n"
)

GPS_LAT = -6.200
GPS_LON = 106.800


class FakeGPS:
    def __init__(self, lat=GPS_LAT, lon=GPS_LON, fail_after=None):
        self.lat = lat
        self.lon = lon
        self.fail_after = fail_after
        self.calls = 0

    def get_location(self):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise GPSError("fake gps failure")
        return GPSLocation(latitude=self.lat, longitude=self.lon)

    def move_to(self, lat: float, lon: float):
        """Move GPS to a new location."""
        self.lat = lat
        self.lon = lon


class MovingGPS(FakeGPS):
    """FakeGPS that cycles through a list of locations."""

    def __init__(self, locations, fail_after=None):
        super().__init__(fail_after=fail_after)
        self.locations = locations
        self.index = 0

    def get_location(self):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise GPSError("fake gps failure")
        loc = self.locations[self.index % len(self.locations)]
        self.index += 1
        return GPSLocation(latitude=loc[0], longitude=loc[1])

    def is_available(self):
        return True


class FakeCLI:
    def __init__(self, error=None):
        self.error = error

    def execute(self, band, timeout):
        if self.error:
            raise self.error
        return SimpleNamespace(results=[])


@pytest.fixture
def fast_settings(monkeypatch):
    import app.core.mission_executor as me

    real = get_settings()
    fast = real.model_copy(
        update={
            "MISSION_POLL_INTERVAL": 0.05,
            "MISSION_START_GPS_TIMEOUT": 1,
            "MISSION_CLI_TIMEOUT": 1,
            "MISSION_SCAN_INTERVAL_SEC": 0.2,
            "MISSION_SCAN_MIN_FOR_VISITED": 1,
            "MISSION_SCAN_MAX_PER_TOWER": 2,
        }
    )
    monkeypatch.setattr(me, "get_settings", lambda: fast)
    return fast


# Patch band validator at module load time so tests work without USB ports
# (No longer needed since band was removed from Mission schema; kept for backward compat)
_OriginalBandPatch = None


@pytest.fixture
def api(db_session, monkeypatch):
    import app.core.mission_executor as me
    from fastapi.testclient import TestClient
    from app.api.dependencies.providers import get_gps_provider

    original_session_local = me.SessionLocal
    me.SessionLocal = TestingSessionLocal

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fake_gps = FakeGPS()
    app.dependency_overrides[get_gps_provider] = lambda: fake_gps

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        me.SessionLocal = original_session_local


@pytest.fixture
def executor(api, fast_settings):
    executor = api.app.state.mission_executor
    gps = FakeGPS()
    executor.gps_provider = gps
    cli = FakeCLI()

    def scan_factory(db):
        return ScanService(db=db, cli_adapter=cli, gps_provider=executor.gps_provider)

    executor._scan_factory = scan_factory
    return executor


def make_planned(db, csv=CSV_1, radius=50, status="IDLE", name="Exec Mission", band=None):
    mission = Mission(name=name, status=status, radius_meters=radius, band=band)
    db.add(mission)
    db.commit()
    db.refresh(mission)
    LocationService(db).upload(mission.id, csv.encode())
    MissionPlannerService(db, gps_provider=FakeGPS()).plan(mission.id)
    db.commit()
    db.refresh(mission)
    db.commit()
    return mission


def wait_for(client, mission_id, expected_statuses, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/missions/{mission_id}/status")
        assert resp.status_code == 200
        if resp.json()["status"] in expected_statuses:
            return resp.json()
        time.sleep(0.05)
    raise AssertionError(
        f"mission {mission_id} did not reach {expected_statuses}: {resp.json()}"
    )


def stop_and_wait(client, mission_id, timeout=10.0):
    resp = client.post(f"/api/v1/missions/{mission_id}/stop")
    assert resp.status_code == 200
    status = wait_for(client, mission_id, {"STOPPED"}, timeout=timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and status["active"]:
        status = client.get(f"/api/v1/missions/{mission_id}/status").json()
        time.sleep(0.05)
    return status
