import pytest
from datetime import datetime

from app.db.models.mission import Mission
from app.db.models.mission_location import MissionLocation
from app.repositories.scan_session_repository import ScanSessionRepository
from app.repositories.scan_result_repository import ScanResultRepository


class TestMissionScanRepository:
    def test_u01_get_mission_flat_returns_only_linked_sessions(self, db_session):
        repo = ScanResultRepository(db_session)

        m1 = Mission(name="m1")
        db_session.add(m1)
        db_session.commit()
        loc1 = MissionLocation(mission_id=m1.id, cellular_tower_id="T1", latitude=-6.2, longitude=106.84)
        db_session.add(loc1)
        db_session.commit()

        m2 = Mission(name="m2")
        db_session.add(m2)
        db_session.commit()
        loc2 = MissionLocation(mission_id=m2.id, cellular_tower_id="T2", latitude=-6.3, longitude=106.85)
        db_session.add(loc2)
        db_session.commit()

        s_repo = ScanSessionRepository(db_session)
        s_a = s_repo.create(band="8", latitude=-6.2, longitude=106.84, mission_location_id=loc1.id)
        r_repo = ScanResultRepository(db_session)
        r_repo.create(session_id=s_a.id, operator_name="A", rat="LTE", status="OK")

        s_b = s_repo.create(band="5", latitude=-6.3, longitude=106.85, mission_location_id=loc2.id)
        r_repo.create(session_id=s_b.id, operator_name="B", rat="GSM", status="OK")

        s_manual = s_repo.create(band="8")
        r_repo.create(session_id=s_manual.id, operator_name="Manual", rat="LTE", status="OK")

        results, total = repo.get_mission_flat(m1.id)
        assert total == 1
        assert len(results) == 1
        # Verify linked session's ID matches
        assert results[0].session_id == s_a.id

        results, total = repo.get_mission_flat(m2.id)
        assert total == 1
        assert len(results) == 1
        assert results[0].session_id == s_b.id

        # Manual scan not in m1
        results, _ = repo.get_mission_flat(m1.id)
        assert all(r.session_id != s_manual.id for r in results)

    def test_u02_get_mission_flat_search_filter(self, db_session):
        repo = ScanResultRepository(db_session)

        mission = Mission(name="test")
        db_session.add(mission)
        db_session.commit()
        loc = MissionLocation(mission_id=mission.id, cellular_tower_id="T1", latitude=-6.2, longitude=106.84)
        db_session.add(loc)
        db_session.commit()

        sess = ScanSessionRepository(db_session).create(
            band="8", latitude=-6.2, longitude=106.84, mission_location_id=loc.id
        )
        ScanResultRepository(db_session).create(session_id=sess.id, operator_name="Telkomsel", mcc="510", mnc="10", rat="LTE", status="OK")

        results, _ = repo.get_mission_flat(mission.id, search="8")
        assert len(results) == 1

        results, _ = repo.get_mission_flat(mission.id, search="Telkomsel")
        assert len(results) == 1

        results, _ = repo.get_mission_flat(mission.id, search="510")
        assert len(results) == 1

        results, _ = repo.get_mission_flat(mission.id, search="xyz")
        assert len(results) == 0

    def test_u03_get_mission_flat_rat_filter(self, db_session):
        repo = ScanResultRepository(db_session)

        mission = Mission(name="test")
        db_session.add(mission)
        db_session.commit()
        loc = MissionLocation(mission_id=mission.id, cellular_tower_id="T1", latitude=-6.2, longitude=106.84)
        db_session.add(loc)
        db_session.commit()

        # Create three linked scan sessions
        for rat_name in ["LTE", "GSM", "UMTS"]:
            sess = ScanSessionRepository(db_session).create(
                band=rat_name, latitude=-6.2, longitude=106.84, mission_location_id=loc.id
            )
            ScanResultRepository(db_session).create(session_id=sess.id, operator_name=rat_name, rat=rat_name, status="OK")

        # All rats (no filter) returns 3
        results, total = repo.get_mission_flat(mission.id, rat=None)
        assert total == 3
        assert len(results) == 3

        # Filter by a single rat returns 1
        results_lte, total_lte = repo.get_mission_flat(mission.id, rat="LTE")
        assert total_lte == 1
        assert len(results_lte) == 1
        # Verify the returned result actually has rat LTE (check attribute)
        assert results_lte[0].rat == "LTE"

        # "ALL" treated as no filter - test via service conversion
        # In service, rat "ALL" becomes None; repo then returns all
        results_all, _ = repo.get_mission_flat(mission.id, rat=None)  # None means no filter
        assert len(results_all) == 3

    def test_u04_get_mission_flat_time_range_validation(self, db_session):
        from app.services import MissionScanService
        service = MissionScanService(db_session)
        # Validation happens in service, not repo; create dummy mission for testing
        mission = Mission(name="timest")
        db_session.add(mission)
        db_session.commit()

        # Time range validation should raise error when start > end
        with pytest.raises(ValueError) as exc_info:
            service.get_mission_scans(mission.id, start_time=datetime(2026, 1, 2), end_time=datetime(2026, 1, 1))
        assert "cannot be greater" in str(exc_info.value).lower()

    def test_u05_get_mission_flat_pagination(self, db_session):
        repo = ScanResultRepository(db_session)

        mission = Mission(name="test")
        db_session.add(mission)
        db_session.commit()
        loc = MissionLocation(mission_id=mission.id, cellular_tower_id="T1", latitude=-6.2, longitude=106.84)
        db_session.add(loc)
        db_session.commit()

        for i in range(25):
            sess = ScanSessionRepository(db_session).create(
                band=str(i+1), latitude=-6.2, longitude=106.84, mission_location_id=loc.id
            )
            ScanResultRepository(db_session).create(session_id=sess.id, operator_name=f"R{i}", rat="LTE", status="OK")

        db_session.commit()

        results, total = repo.get_mission_flat(mission.id, page=1, page_size=10)
        assert total == 25
        assert len(results) == 10
        # They are ordered by scan_time desc, so the newest session (highest id) is first
        assert results[0].session_id > results[9].session_id  # desc by scan_time

        results, _ = repo.get_mission_flat(mission.id, page=2, page_size=10)
        assert len(results) == 10

        results, _ = repo.get_mission_flat(mission.id, page=3, page_size=10)
        assert len(results) == 5

    def test_u06_service_mission_exists_check(self, db_session):
        from app.services import MissionScanService
        service = MissionScanService(db_session)
        try:
            service.get_mission_scans(9999)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert str(e) == "Mission not found"

    def test_u07_csv_header_exact_columns(self, db_session):
        mission = Mission(name="test")
        db_session.add(mission)
        db_session.commit()
        loc = MissionLocation(
            mission_id=mission.id,
            cellular_tower_id="TOW_ID",
            cellular_tower_name="BTS Name",
            latitude=-6.2,
            longitude=106.84,
        )
        db_session.add(loc)
        db_session.commit()

        sess = ScanSessionRepository(db_session).create(
            band="8", latitude=-6.2, longitude=106.84, mission_location_id=loc.id
        )
        ScanResultRepository(db_session).create(
            session_id=sess.id, operator_name="Test", mcc="123", mnc="45", rat="LTE", status="OK"
        )
        db_session.commit()

        from app.services import MissionScanService
        service = MissionScanService(db_session)
        csv = service.get_mission_csv(mission.id)
        # Normalize line endings for comparison
        header = csv.replace("\r", "").split("\n")[0]
        expected = "scan_time,latitude,longitude,operator_name,mcc,mnc,rat,cellular_tower_id,cellular_tower_name"
        assert header == expected

    def test_u08_empty_mission_no_scans(self, db_session):
        mission = Mission(name="empty")
        db_session.add(mission)
        db_session.commit()

        from app.services import MissionScanService
        service = MissionScanService(db_session)
        resp = service.get_mission_scans(mission.id)
        assert resp.total == 0
        assert len(resp.items) == 0
        assert resp.page == 1
        assert resp.page_size == 10
        assert resp.total_pages == 1

    def test_u09_schema_mission_location_id_field_exists(self):
        from app.schemas.scan import ScanResultFlatResponse
        from datetime import datetime

        # Just verify the field is present and accepts None
        f = ScanResultFlatResponse(
            id=1,
            scan_session_id=1,
            scan_time=datetime.now(),
            band="8",
            created_at=datetime.now(),
            mission_location_id=None,
        )
        assert f.mission_location_id is None
