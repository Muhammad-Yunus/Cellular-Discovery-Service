import pytest

from app.db.models import Mission, MissionLocation, ScanSession

from tests.conftest import CSV_1, CSV_5, FakeGPS, FakeCLI, make_planned, stop_and_wait, wait_for


class TestStart:
    def test_u01_start_runs_mission(self, api, executor, db_session):
        mission = make_planned(db_session)
        executor.gps_provider = FakeGPS(lat=0, lon=0)

        resp = api.post(f"/api/v1/missions/{mission.id}/start")

        assert resp.status_code == 200
        assert resp.json()["status"] == "RUNNING"
        status = wait_for(api, mission.id, {"RUNNING"})
        assert status["active"] is True
        assert status["started_at"] is not None
        stop_and_wait(api, mission.id)

    def test_u02_start_without_planned_locations(self, api, executor, db_session):
        mission = Mission(name="Empty", status="IDLE", radius_meters=50)
        db_session.add(mission)
        db_session.commit()
        db_session.refresh(mission)
        db_session.commit()

        resp = api.post(f"/api/v1/missions/{mission.id}/start")

        assert resp.status_code == 422
        assert resp.json()["detail"] == "Mission has no planned locations. Run plan first"

    def test_u03_start_when_another_running(self, api, executor, db_session):
        first = make_planned(db_session, csv=CSV_1, name="First")
        second = make_planned(db_session, csv=CSV_1, name="Second")
        executor.gps_provider = FakeGPS(lat=0, lon=0)
        api.post(f"/api/v1/missions/{first.id}/start")
        wait_for(api, first.id, {"RUNNING"})

        resp = api.post(f"/api/v1/missions/{second.id}/start")

        assert resp.status_code == 409
        assert "already running" in resp.json()["detail"]
        stop_and_wait(api, first.id)

    def test_u04_start_when_already_running(self, api, executor, db_session):
        mission = make_planned(db_session)
        executor.gps_provider = FakeGPS(lat=0, lon=0)
        api.post(f"/api/v1/missions/{mission.id}/start")
        wait_for(api, mission.id, {"RUNNING"})

        resp = api.post(f"/api/v1/missions/{mission.id}/start")

        assert resp.status_code == 409
        stop_and_wait(api, mission.id)

    @pytest.mark.parametrize(
        "status",
        ["STARTING", "PAUSED", "STOPPED", "COMPLETED", "FAILED", "PLANNING"],
    )
    def test_u05_start_invalid_state(self, api, executor, db_session, status):
        mission = make_planned(db_session)
        mission.status = status
        db_session.commit()
        db_session.refresh(mission)
        db_session.commit()

        resp = api.post(f"/api/v1/missions/{mission.id}/start")

        assert resp.status_code == 409
        assert f"it is {status}" in resp.json()["detail"]

    def test_e01_start_unknown_mission(self, api, executor):
        resp = api.post("/api/v1/missions/99999/start")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Mission not found"


class TestPauseResume:
    def test_u06_pause_running(self, api, executor, db_session):
        mission = make_planned(db_session)
        executor.gps_provider = FakeGPS(lat=0, lon=0)
        api.post(f"/api/v1/missions/{mission.id}/start")
        wait_for(api, mission.id, {"RUNNING"})

        resp = api.post(f"/api/v1/missions/{mission.id}/pause")

        assert resp.status_code == 200
        assert resp.json()["status"] == "PAUSED"
        status = wait_for(api, mission.id, {"PAUSED"})
        assert status["active"] is True
        stop_and_wait(api, mission.id)

    def test_u07_pause_not_running(self, api, executor, db_session):
        mission = make_planned(db_session)

        resp = api.post(f"/api/v1/missions/{mission.id}/pause")

        assert resp.status_code == 409
        assert resp.json()["detail"] == "Cannot pause mission while it is READY"

    def test_u08_resume_paused(self, api, executor, db_session):
        mission = make_planned(db_session)
        executor.gps_provider = FakeGPS(lat=0, lon=0)
        api.post(f"/api/v1/missions/{mission.id}/start")
        wait_for(api, mission.id, {"RUNNING"})
        api.post(f"/api/v1/missions/{mission.id}/pause")
        wait_for(api, mission.id, {"PAUSED"})

        resp = api.post(f"/api/v1/missions/{mission.id}/resume")

        assert resp.status_code == 200
        assert resp.json()["status"] == "RUNNING"
        wait_for(api, mission.id, {"RUNNING"})
        stop_and_wait(api, mission.id)

    def test_u09_resume_not_paused(self, api, executor, db_session):
        mission = make_planned(db_session)

        resp = api.post(f"/api/v1/missions/{mission.id}/resume")

        assert resp.status_code == 409
        assert resp.json()["detail"] == "Cannot resume mission while it is READY"


class TestStop:
    def test_u10_stop_running(self, api, executor, db_session):
        mission = make_planned(db_session)
        executor.gps_provider = FakeGPS(lat=0, lon=0)
        api.post(f"/api/v1/missions/{mission.id}/start")
        wait_for(api, mission.id, {"RUNNING"})

        resp = api.post(f"/api/v1/missions/{mission.id}/stop")

        assert resp.status_code == 200
        assert resp.json()["status"] == "STOPPED"
        status = wait_for(api, mission.id, {"STOPPED"})
        assert status["stopped_at"] is not None
        assert status["active"] is False

    def test_u11_stop_not_active(self, api, executor, db_session):
        mission = make_planned(db_session)

        resp = api.post(f"/api/v1/missions/{mission.id}/stop")

        assert resp.status_code == 409
        assert resp.json()["detail"] == "Cannot stop mission while it is READY"


class TestStatusAndLogs:
    def test_u12_status_progress(self, api, executor, db_session):
        mission = make_planned(db_session, csv=CSV_5)

        resp = api.get(f"/api/v1/missions/{mission.id}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["mission_id"] == mission.id
        assert data["name"] == mission.name
        assert data["status"] == "READY"
        assert data["total_locations"] == 5
        assert data["visited_locations"] == 0
        assert data["progress_percent"] == 0.0

    def test_u13_logs_captured(self, api, executor, db_session):
        mission = make_planned(db_session)
        executor.gps_provider = FakeGPS(lat=0, lon=0)
        api.post(f"/api/v1/missions/{mission.id}/start")
        wait_for(api, mission.id, {"RUNNING"})

        logs = api.get(f"/api/v1/missions/{mission.id}/logs")

        assert logs.status_code == 200
        messages = [entry["message"] for entry in logs.json()]
        assert any("starting" in message for message in messages)
        stop_and_wait(api, mission.id)

    def test_e02_status_unknown(self, api, executor):
        resp = api.get("/api/v1/missions/99999/status")

        assert resp.status_code == 404

    def test_e03_logs_unknown(self, api, executor):
        resp = api.get("/api/v1/missions/99999/logs")

        assert resp.status_code == 404


class TestBackgroundExecution:
    def test_u14_background_completion(self, api, executor, db_session):
        mission = make_planned(db_session, csv=CSV_5, radius=20000)

        api.post(f"/api/v1/missions/{mission.id}/start")
        status = wait_for(api, mission.id, {"COMPLETED"}, timeout=15.0)

        assert status["progress_percent"] == 100.0
        assert status["visited_locations"] == 5

        locations = (
            db_session.query(MissionLocation)
            .filter(MissionLocation.mission_id == mission.id)
            .all()
        )
        assert all(loc.status == "VISITED" for loc in locations)
        assert all(loc.scan_session_id is not None for loc in locations)
        sessions = (
            db_session.query(ScanSession)
            .filter(ScanSession.mission_location_id.isnot(None))
            .count()
        )
        assert sessions == 5

    def test_u15_start_without_gps(self, api, executor, db_session):
        executor.gps_provider = FakeGPS(fail_after=0)
        mission = make_planned(db_session)

        resp = api.post(f"/api/v1/missions/{mission.id}/start")

        assert resp.status_code == 503
        status = wait_for(api, mission.id, {"FAILED"})
        assert "GPS" in status["last_error"]

    def test_u15_gps_failure_mid_run(self, api, executor, db_session, fast_settings):
        executor.gps_provider = FakeGPS(fail_after=2)
        mission = make_planned(db_session)

        api.post(f"/api/v1/missions/{mission.id}/start")
        status = wait_for(api, mission.id, {"FAILED"}, timeout=15.0)

        assert status["gps_failure_count"] >= 2
        assert "GPS" in status["last_error"]

    def test_u16_scan_failure_skips_location(self, api, executor, db_session):
        cli = FakeCLI(error=RuntimeError("scan exploded"))
        gps = FakeGPS()

        def scan_factory(db):
            return ScanService(db=db, cli_adapter=cli, gps_provider=gps)

        executor._scan_factory = scan_factory
        executor.gps_provider = gps
        mission = make_planned(db_session, csv=CSV_1, radius=50)

        api.post(f"/api/v1/missions/{mission.id}/start")
        status = wait_for(api, mission.id, {"COMPLETED"}, timeout=15.0)

        loc = (
            db_session.query(MissionLocation)
            .filter(MissionLocation.mission_id == mission.id)
            .one()
        )
        assert loc.status == "SKIPPED"
        assert status["visited_locations"] == 0
