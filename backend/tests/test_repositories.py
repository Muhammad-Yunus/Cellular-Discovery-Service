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
            band="8",
            latitude=-6.150676643667096,
            longitude=106.89665223346297,
        )

        assert session.id is not None
        assert session.band == "8"
        assert session.latitude == -6.150676643667096

    def test_get_by_id(self, db_session):
        self.repo = ScanSessionRepository(db_session)

        session = self.repo.create(band="8")
        found = self.repo.get_by_id(session.id)

        assert found is not None
        assert found.id == session.id

    def test_get_by_id_not_found(self, db_session):
        self.repo = ScanSessionRepository(db_session)

        found = self.repo.get_by_id(9999)

        assert found is None

    def test_get_all(self, db_session):
        self.repo = ScanSessionRepository(db_session)

        self.repo.create(band="8")
        self.repo.create(band="20")

        sessions, total = self.repo.get_all()

        assert total == 2
        assert len(sessions) == 2

    def test_delete_session(self, db_session):
        self.repo = ScanSessionRepository(db_session)

        session = self.repo.create(band="8")
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

        session = self.session_repo.create(band="8")
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

        session = self.session_repo.create(band="8")
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

        session = self.session_repo.create(band="8")
        self.repo.create(session_id=session.id, operator_name="Telkomsel")
        self.repo.create(session_id=session.id, operator_name="XL")

        results = self.repo.get_by_session_id(session.id)

        assert len(results) == 2

    # ------------------------------------------------------------------
    # get_all_flat sorting (ASC + DESC across operator_name, mcc, mnc, rat, scan_time)
    # ------------------------------------------------------------------

    def _seed_flat_sort_fixture(self, db_session):
        """Seed 5 sessions × 5 results. Every sortable field has a distinct
        value so tie-breakers never influence the order. Return the created
        results ordered by ascending scan_time (= insertion order)."""
        self.session_repo = ScanSessionRepository(db_session)
        self.repo = ScanResultRepository(db_session)

        # Distinct values for each sortable field, alphabetic/lexical order:
        # operator_name ASC = Indosat < Smartfren < Telkomsel < Three < XL
        # mcc             ASC = 310 < 401 < 502 < 603 < 704
        # mnc             ASC = 10 < 20 < 30 < 40 < 50
        # rat             ASC = 2G < 3G < 4G < 5G < LTE
        plan = [
            # (operator_name, mcc, mnc, rat)
            ("Telkomsel", "502", "30", "4G"),
            ("XL",        "704", "50", "3G"),
            ("Indosat",   "310", "10", "5G"),
            ("Three",     "603", "40", "2G"),
            ("Smartfren", "401", "20", "LTE"),
        ]
        sessions = []
        results = []
        for tty, payload in enumerate(plan):
            s = self.session_repo.create(band=str(tty+1))
            sessions.append(s)
            r = self.repo.create(
                session_id=s.id,
                operator_name=payload[0],
                mcc=payload[1],
                mnc=payload[2],
                rat=payload[3],
            )
            results.append(r)
        return results

    @pytest.mark.parametrize(
        "sort_key, expected_order",
        [
            ("operator_name", ["Indosat", "Smartfren", "Telkomsel", "Three", "XL"]),
            ("mcc",           ["Indosat", "Smartfren", "Telkomsel", "Three", "XL"]),
            ("mnc",           ["Indosat", "Smartfren", "Telkomsel", "Three", "XL"]),
            ("rat",           ["Three", "XL", "Telkomsel", "Indosat", "Smartfren"]),
            ("scan_time",     ["Smartfren", "Three", "Indosat", "XL", "Telkomsel"]),
        ],
    )
    def test_get_all_flat_sort_asc(self, db_session, sort_key, expected_order):
        self._seed_flat_sort_fixture(db_session)

        results, total = ScanResultRepository(db_session).get_all_flat(
            page=1, page_size=10, sort=sort_key
        )
        assert total == 5
        actual = [r.operator_name for r in results]
        assert actual == expected_order

    @pytest.mark.parametrize(
        "sort_key, expected_order",
        [
            ("-operator_name", ["XL", "Three", "Telkomsel", "Smartfren", "Indosat"]),
            ("-mcc",           ["XL", "Three", "Telkomsel", "Smartfren", "Indosat"]),
            ("-mnc",           ["XL", "Three", "Telkomsel", "Smartfren", "Indosat"]),
            ("-rat",           ["Smartfren", "Indosat", "Telkomsel", "XL", "Three"]),
            ("-scan_time",     ["Smartfren", "Three", "Indosat", "XL", "Telkomsel"]),
        ],
    )
    def test_get_all_flat_sort_desc(self, db_session, sort_key, expected_order):
        self._seed_flat_sort_fixture(db_session)

        results, total = ScanResultRepository(db_session).get_all_flat(
            page=1, page_size=10, sort=sort_key
        )
        assert total == 5
        actual = [r.operator_name for r in results]
        assert actual == expected_order

    def test_get_all_flat_sort_unknown_field_falls_back_to_scan_time_desc(
        self, db_session
    ):
        self._seed_flat_sort_fixture(db_session)

        results, _ = ScanResultRepository(db_session).get_all_flat(
            page=1, page_size=10, sort="bogus_field"
        )
        # Unknown sort key must fall back to scan_time DESC.
        actual = [r.operator_name for r in results]
        assert actual == ["Smartfren", "Three", "Indosat", "XL", "Telkomsel"]


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
