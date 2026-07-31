import pytest
from sqlalchemy.exc import IntegrityError
from app.db.database import get_db
from app.db.session import SessionLocal, engine
from app.db.models.mission import Mission
from app.db.models.mission_location import MissionLocation
from app.db.models.scan_session import ScanSession


class TestDatabase:
    def test_get_db_generator(self):
        gen = get_db()

        db = next(gen)

        assert db is not None
        assert db.is_active

        try:
            next(gen)
        except StopIteration:
            pass

    def test_session_local_creation(self):
        session = SessionLocal()

        assert session is not None
        session.close()

    def test_engine_creation(self):
        assert engine is not None
        assert engine.url is not None


class TestMissionModels:
    def test_u01_mission_status_check_rejects_invalid(self, db_session):
        mission = Mission(name="Bad", status="NONSENSE")

        db_session.add(mission)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_u02_mission_location_requires_mission_and_unique_tower(self, db_session):
        loc = MissionLocation(cellular_tower_id="T1", latitude=-6.2, longitude=106.8)

        db_session.add(loc)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

        mission = Mission(name="M", status="IDLE")
        db_session.add(mission)
        db_session.flush()

        db_session.add_all(
            [
                MissionLocation(
                    mission_id=mission.id, cellular_tower_id="T1",
                    latitude=-6.2, longitude=106.8,
                ),
                MissionLocation(
                    mission_id=mission.id, cellular_tower_id="T1",
                    latitude=-6.3, longitude=106.9,
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_u03_mission_one_to_many(self, db_session):
        mission = Mission(name="M", status="IDLE")
        db_session.add(mission)
        db_session.flush()

        db_session.add_all(
            [
                MissionLocation(
                    mission_id=mission.id, cellular_tower_id=f"T{i}",
                    latitude=-6.2 - i * 0.1, longitude=106.8 + i * 0.1,
                )
                for i in range(3)
            ]
        )
        db_session.commit()

        assert len(mission.locations) == 3

    def test_u04_scan_session_mission_location_id_nullable(self, db_session):
        legacy = ScanSession(tty_port="/dev/ttyUSB0")

        db_session.add(legacy)
        db_session.commit()

        assert legacy.mission_location_id is None
        assert legacy.id is not None

    def test_u05_relationship_navigation_and_ordering(self, db_session):
        mission = Mission(name="M", status="IDLE")
        db_session.add(mission)
        db_session.flush()

        db_session.add_all(
            [
                MissionLocation(
                    mission_id=mission.id, cellular_tower_id="T1",
                    latitude=-6.2, longitude=106.8, sequence_order=3,
                ),
                MissionLocation(
                    mission_id=mission.id, cellular_tower_id="T2",
                    latitude=-6.3, longitude=106.9, sequence_order=1,
                ),
                MissionLocation(
                    mission_id=mission.id, cellular_tower_id="T3",
                    latitude=-6.4, longitude=107.0, sequence_order=2,
                ),
            ]
        )
        session = ScanSession(tty_port="/dev/ttyUSB0")
        db_session.add(session)
        db_session.commit()

        assert [loc.cellular_tower_id for loc in mission.locations] == ["T2", "T3", "T1"]

        first = mission.locations[0]
        assert first.mission.id == mission.id

        first.scan_session_id = session.id
        db_session.commit()
        assert first.scan_session.id == session.id

        session.mission_location_id = first.id
        db_session.commit()
        assert session.mission_location.id == first.id

    def test_u06_fk_cascade_deletes_locations(self, db_session):
        mission = Mission(name="M", status="IDLE")
        db_session.add(mission)
        db_session.flush()
        db_session.add_all(
            [
                MissionLocation(
                    mission_id=mission.id, cellular_tower_id=f"T{i}",
                    latitude=-6.2 - i * 0.1, longitude=106.8 + i * 0.1,
                )
                for i in range(3)
            ]
        )
        db_session.commit()

        db_session.delete(mission)
        db_session.commit()

        assert db_session.query(MissionLocation).filter_by(mission_id=mission.id).count() == 0

    def test_u07_scan_session_id_unique(self, db_session):
        mission = Mission(name="M", status="IDLE")
        session = ScanSession(tty_port="/dev/ttyUSB0")
        db_session.add_all([mission, session])
        db_session.flush()

        db_session.add_all(
            [
                MissionLocation(
                    mission_id=mission.id, cellular_tower_id="T1",
                    latitude=-6.2, longitude=106.8, scan_session_id=session.id,
                ),
                MissionLocation(
                    mission_id=mission.id, cellular_tower_id="T2",
                    latitude=-6.3, longitude=106.9, scan_session_id=session.id,
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_u08_coordinate_check_rejects_invalid(self, db_session):
        mission = Mission(name="M", status="IDLE")
        db_session.add(mission)
        db_session.flush()

        db_session.add(
            MissionLocation(
                mission_id=mission.id, cellular_tower_id="T1",
                latitude=95.0, longitude=106.8,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_u09_circular_fk_set_null_on_location_delete(self, db_session):
        mission = Mission(name="M", status="IDLE")
        db_session.add(mission)
        db_session.flush()

        start = MissionLocation(
            mission_id=mission.id, cellular_tower_id="T1",
            latitude=-6.2, longitude=106.8,
        )
        current = MissionLocation(
            mission_id=mission.id, cellular_tower_id="T2",
            latitude=-6.3, longitude=106.9,
        )
        db_session.add_all([start, current])
        db_session.commit()

        mission.start_location_id = start.id
        mission.current_location_id = current.id
        db_session.commit()

        db_session.delete(start)
        db_session.commit()

        db_session.refresh(mission)
        assert mission.start_location_id is None
        assert mission.current_location_id == current.id
