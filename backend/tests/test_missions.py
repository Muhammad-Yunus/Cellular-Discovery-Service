import pytest
from fastapi import HTTPException
from app.db.models import Mission, MissionLocation, ScanSession
from app.repositories import MissionRepository, MissionLocationRepository
from app.services import LocationService, MissionService
from app.schemas.mission import MissionCreate, MissionStatus, MissionUpdate

CSV_HEADER = "cellular_tower_id,cellular_tower_name,latitude,longitude\n"
CSV_VALID = (
    CSV_HEADER
    + "TWR-001,Jakarta Pusat,-6.2088,106.8456\n"
    + "TWR-002,Jakarta Selatan,-6.2615,106.8106\n"
    + "TWR-003,Jakarta Barat,-6.1688,106.7582\n"
)


def make_mission(db, status="IDLE", name="Mission X"):
    mission = Mission(name=name, status=status)
    db.add(mission)
    db.commit()
    db.refresh(mission)
    return mission


def upload_locations(db, mission_id):
    return LocationService(db).upload(mission_id, CSV_VALID.encode())


class TestMissionRepository:
    def test_u01_repo_create_defaults(self, db_session):
        mission = MissionRepository(db_session).create(name="M")

        assert mission.status == "IDLE"
        assert mission.total_locations == 0
        assert mission.visited_locations == 0

    def test_u14_status_enum_matches_db_check(self):
        values = {s.value for s in MissionStatus}
        expected = {
            "IDLE", "PLANNING", "READY", "STARTING", "RUNNING",
            "PAUSED", "COMPLETED", "STOPPED", "FAILED",
        }
        assert values == expected

    def test_u04_repo_list_status_filter(self, db_session):
        repo = MissionRepository(db_session)
        make_mission(db_session, status="IDLE", name="A")
        make_mission(db_session, status="RUNNING", name="B")
        make_mission(db_session, status="COMPLETED", name="C")

        idle, total = repo.list(page=1, page_size=10, status="IDLE")

        assert total == 1
        assert all(m.status == "IDLE" for m in idle)

    def test_u05_repo_list_search(self, db_session):
        repo = MissionRepository(db_session)
        make_mission(db_session, status="IDLE", name="Jakarta Utara Sweep")
        make_mission(db_session, status="IDLE", name="Bandung Test")

        results, total = repo.list(page=1, page_size=10, search="jakarta")

        assert total == 1
        assert results[0].name == "Jakarta Utara Sweep"


class TestMissionService:
    def test_u06_get_detail_ordering_and_progress(self, db_session):
        service = MissionService(db_session)
        mission = make_mission(db_session)
        upload_locations(db_session, mission.id)

        locs = db_session.query(MissionLocation).filter_by(mission_id=mission.id).all()
        mission.total_locations = 10
        mission.visited_locations = 3
        locs[0].sequence_order = 3
        locs[1].sequence_order = 1
        locs[2].sequence_order = 2
        db_session.commit()

        detail = service.get_detail(mission.id)

        assert [l.cellular_tower_id for l in detail.locations] == [
            locs[1].cellular_tower_id, locs[2].cellular_tower_id, locs[0].cellular_tower_id,
        ]
        assert detail.progress_percent == 30.0

    def test_u07_update_field_patch(self, db_session):
        service = MissionService(db_session)
        mission = make_mission(db_session)

        result = service.update(
            mission.id,
            MissionUpdate(name="Renamed", description="notes", radius_meters=30, tty_port="/dev/ttyUSB1"),
        )

        assert result.name == "Renamed"
        assert result.description == "notes"
        assert result.radius_meters == 30
        assert result.tty_port == "/dev/ttyUSB1"
        assert result.status == "IDLE"

    def test_u08_update_clear_tty_and_start(self, db_session):
        service = MissionService(db_session)
        mission = make_mission(db_session)
        upload_locations(db_session, mission.id)
        first = db_session.query(MissionLocation).filter_by(mission_id=mission.id).first()
        mission.start_location_id = first.id
        mission.tty_port = "/dev/ttyUSB2"
        db_session.commit()

        service.update(mission.id, MissionUpdate(tty_port=None, start_location_id=None))
        db_session.refresh(mission)

        assert mission.tty_port is None
        assert mission.start_location_id is None

    def test_u09_update_foreign_start_location(self, db_session):
        service = MissionService(db_session)
        mission = make_mission(db_session)
        other = make_mission(db_session, name="Other")
        upload_locations(db_session, other.id)
        foreign_loc = db_session.query(MissionLocation).filter_by(mission_id=other.id).first()

        with pytest.raises(HTTPException) as exc:
            service.update(mission.id, MissionUpdate(start_location_id=foreign_loc.id))

        assert exc.value.status_code == 422
        assert "start_location_id does not belong to this mission" in exc.value.detail

    def test_u10_update_on_running(self, db_session):
        service = MissionService(db_session)
        mission = make_mission(db_session, status="RUNNING")

        with pytest.raises(HTTPException) as exc:
            service.update(mission.id, MissionUpdate(name="nope"))

        assert exc.value.status_code == 409

    def test_u11_update_structural_clears_sequence(self, db_session):
        service = MissionService(db_session)
        mission = make_mission(db_session)
        upload_locations(db_session, mission.id)
        for i, loc in enumerate(
            db_session.query(MissionLocation).filter_by(mission_id=mission.id).all()
        ):
            loc.sequence_order = i + 1
        db_session.commit()

        service.update(mission.id, MissionUpdate(radius_meters=50))

        seqs = [
            loc.sequence_order
            for loc in db_session.query(MissionLocation).filter_by(mission_id=mission.id).all()
        ]
        assert all(s is None for s in seqs)

    def test_u12_delete_on_active_statuses(self, db_session):
        service = MissionService(db_session)
        for status in ("RUNNING", "PAUSED", "STARTING"):
            mission = make_mission(db_session, status=status)

            with pytest.raises(HTTPException) as exc:
                service.delete(mission.id)

            assert exc.value.status_code == 409

    def test_u13_delete_allowed_statuses_cascades(self, db_session):
        service = MissionService(db_session)
        for status in ("IDLE", "STOPPED", "COMPLETED"):
            mission = make_mission(db_session, status=status)
            upload_locations(db_session, mission.id)

            assert service.delete(mission.id) is True

            assert db_session.query(Mission).filter_by(id=mission.id).count() == 0
            assert db_session.query(MissionLocation).filter_by(mission_id=mission.id).count() == 0


class TestMissionEndpoints:
    def test_e01_create_then_list(self, client, db_session):
        create = client.post(
            "/api/v1/missions",
            json={"name": "Smoke Mission", "description": "test", "radius_meters": 20},
        )

        assert create.status_code == 201
        data = create.json()
        assert data["status"] == "IDLE"
        assert data["total_locations"] == 0
        assert data["progress_percent"] == 0.0

        listing = client.get("/api/v1/missions")
        assert listing.status_code == 200
        assert listing.json()["total"] == 1

    def test_e02_upload_then_detail(self, client, db_session):
        mission = make_mission(db_session)
        client.post(
            f"/api/v1/missions/{mission.id}/locations/upload",
            files={"file": ("towers.csv", CSV_VALID.encode(), "text/csv")},
        )

        response = client.get(f"/api/v1/missions/{mission.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total_locations"] == 3
        assert len(data["locations"]) == 3

    def test_e03_patch_valid_start_location(self, client, db_session):
        mission = make_mission(db_session)
        upload_locations(db_session, mission.id)
        loc_id = db_session.query(MissionLocation).filter_by(mission_id=mission.id).first().id

        response = client.patch(
            f"/api/v1/missions/{mission.id}",
            json={"start_location_id": loc_id},
        )

        assert response.status_code == 200
        assert response.json()["start_location_id"] == loc_id

    def test_e04_patch_foreign_start_location(self, client, db_session):
        mission = make_mission(db_session)
        other = make_mission(db_session, name="Other")
        upload_locations(db_session, other.id)
        foreign_id = db_session.query(MissionLocation).filter_by(mission_id=other.id).first().id

        response = client.patch(
            f"/api/v1/missions/{mission.id}",
            json={"start_location_id": foreign_id},
        )

        assert response.status_code == 422
        assert "start_location_id does not belong to this mission" in response.json()["detail"]

    def test_e05_patch_on_running(self, client, db_session):
        mission = make_mission(db_session, status="RUNNING")

        response = client.patch(f"/api/v1/missions/{mission.id}", json={"name": "x"})

        assert response.status_code == 409

    def test_e06_delete_keeps_scan_sessions(self, client, db_session):
        mission = make_mission(db_session)
        upload_locations(db_session, mission.id)
        loc = db_session.query(MissionLocation).filter_by(mission_id=mission.id).first()
        session = ScanSession(tty_port="/dev/ttyUSB0")
        db_session.add(session)
        db_session.commit()
        loc.scan_session_id = session.id
        db_session.commit()

        response = client.delete(f"/api/v1/missions/{mission.id}")

        assert response.status_code == 200
        assert response.json()["message"] == "Mission deleted successfully"
        assert db_session.query(Mission).filter_by(id=mission.id).count() == 0
        assert db_session.query(MissionLocation).filter_by(mission_id=mission.id).count() == 0
        assert db_session.query(ScanSession).filter_by(id=session.id).count() == 1
        db_session.refresh(session)
        assert session.mission_location_id is None

    def test_e07_delete_on_running(self, client, db_session):
        mission = make_mission(db_session, status="RUNNING")

        response = client.delete(f"/api/v1/missions/{mission.id}")

        assert response.status_code == 409

    def test_e08_get_missing_mission(self, client):
        response = client.get("/api/v1/missions/99999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Mission not found"

    def test_e09_list_invalid_status(self, client):
        response = client.get("/api/v1/missions?status=BOGUS")

        assert response.status_code == 422
        assert response.json()["detail"] == "Invalid mission status: BOGUS"

    def test_u02_create_empty_name(self, client):
        response = client.post("/api/v1/missions", json={"name": "   "})

        assert response.status_code == 422
        assert "Mission name is required" in response.json()["detail"][0]["msg"]

    def test_u03_create_zero_radius(self, client):
        response = client.post("/api/v1/missions", json={"name": "M", "radius_meters": 0})

        assert response.status_code == 422
