import pytest
from app.repositories.scan_session_repository import ScanSessionRepository
from app.repositories.scan_result_repository import ScanResultRepository
from app.repositories.setting_repository import SettingRepository


class TestScanSessionRepository:
    def setup_method(self):
        self.repo = None

    def test_create_session(self, db_session):
        self.repo = ScanSessionRepository(db_session)

        session = self.repo.create(
            tty_port="/dev/ttyUSB0",
            latitude=-6.150676643667096,
            longitude=106.89665223346297,
        )

        assert session.id is not None
        assert session.tty_port == "/dev/ttyUSB0"
        assert session.latitude == -6.150676643667096

    def test_get_by_id(self, db_session):
        self.repo = ScanSessionRepository(db_session)

        session = self.repo.create(tty_port="/dev/ttyUSB0")
        found = self.repo.get_by_id(session.id)

        assert found is not None
        assert found.id == session.id

    def test_get_by_id_not_found(self, db_session):
        self.repo = ScanSessionRepository(db_session)

        found = self.repo.get_by_id(9999)

        assert found is None

    def test_get_all(self, db_session):
        self.repo = ScanSessionRepository(db_session)

        self.repo.create(tty_port="/dev/ttyUSB0")
        self.repo.create(tty_port="/dev/ttyUSB1")

        sessions, total = self.repo.get_all()

        assert total == 2
        assert len(sessions) == 2

    def test_delete_session(self, db_session):
        self.repo = ScanSessionRepository(db_session)

        session = self.repo.create(tty_port="/dev/ttyUSB0")
        deleted = self.repo.delete(session.id)

        assert deleted is True
        assert self.repo.get_by_id(session.id) is None

    def test_delete_session_not_found(self, db_session):
        self.repo = ScanSessionRepository(db_session)

        deleted = self.repo.delete(9999)

        assert deleted is False


class TestScanResultRepository:
    def setup_method(self):
        self.repo = None

    def test_create_result(self, db_session):
        self.session_repo = ScanSessionRepository(db_session)
        self.repo = ScanResultRepository(db_session)

        session = self.session_repo.create(tty_port="/dev/ttyUSB0")
        result = self.repo.create(
            session_id=session.id,
            operator_name="Telkomsel",
            mcc="510",
            mnc="10",
            rat="4G",
            status="active",
        )

        assert result.id is not None
        assert result.operator_name == "Telkomsel"

    def test_create_bulk(self, db_session):
        self.session_repo = ScanSessionRepository(db_session)
        self.repo = ScanResultRepository(db_session)

        session = self.session_repo.create(tty_port="/dev/ttyUSB0")
        results = self.repo.create_bulk(
            session_id=session.id,
            results=[
                {"operator_name": "Telkomsel", "mcc": "510", "mnc": "10"},
                {"operator_name": "XL", "mcc": "510", "mnc": "11"},
            ],
        )

        assert len(results) == 2

    def test_get_by_session_id(self, db_session):
        self.session_repo = ScanSessionRepository(db_session)
        self.repo = ScanResultRepository(db_session)

        session = self.session_repo.create(tty_port="/dev/ttyUSB0")
        self.repo.create(session_id=session.id, operator_name="Telkomsel")
        self.repo.create(session_id=session.id, operator_name="XL")

        results = self.repo.get_by_session_id(session.id)

        assert len(results) == 2


class TestSettingRepository:
    def setup_method(self):
        self.repo = None

    def test_set_and_get_value(self, db_session):
        self.repo = SettingRepository(db_session)

        self.repo.set_value("test_key", "test_value")
        value = self.repo.get_value("test_key")

        assert value == "test_value"

    def test_get_value_with_default(self, db_session):
        self.repo = SettingRepository(db_session)

        value = self.repo.get_value("nonexistent", "default")

        assert value == "default"

    def test_set_value_update(self, db_session):
        self.repo = SettingRepository(db_session)

        self.repo.set_value("key", "value1")
        self.repo.set_value("key", "value2")
        value = self.repo.get_value("key")

        assert value == "value2"

    def test_get_all(self, db_session):
        self.repo = SettingRepository(db_session)

        self.repo.set_value("key1", "value1")
        self.repo.set_value("key2", "value2")

        settings = self.repo.get_all()

        assert len(settings) == 2

    def test_delete(self, db_session):
        self.repo = SettingRepository(db_session)

        self.repo.set_value("key", "value")
        deleted = self.repo.delete("key")

        assert deleted is True
        assert self.repo.get_value("key") is None

    def test_delete_not_found(self, db_session):
        self.repo = SettingRepository(db_session)

        deleted = self.repo.delete("nonexistent")

        assert deleted is False
