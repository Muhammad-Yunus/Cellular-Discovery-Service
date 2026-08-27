import pytest
from unittest.mock import MagicMock, patch
from app.services.scan_service import ScanService
from app.services.history_service import HistoryService
from app.services.settings_service import SettingsService
from app.cli import CLIScanResponse, CLIScanResult
from app.gps import GPSLocation


class TestScanService:
    def _make_service(self, db_session):
        cli_adapter = MagicMock()
        gps_provider = MagicMock()
        return ScanService(
            db=db_session,
            cli_adapter=cli_adapter,
            gps_provider=gps_provider,
        ), cli_adapter, gps_provider

    def test_execute_scan(self, db_session):
        service, cli_adapter, gps_provider = self._make_service(db_session)

        gps_provider.get_location.return_value = GPSLocation(
            latitude=-6.150676643667096,
            longitude=106.89665223346297,
        )

        cli_adapter.execute.return_value = CLIScanResponse(
            results=[
                CLIScanResult(
                    operator_name="Telkomsel",
                    mcc="510",
                    mnc="10",
                    rat="4G",
                    status="active",
                )
            ],
            raw_output='{"cells": []}',
        )

        result = service.execute_scan(band=8)

        assert result is not None
        assert result.band == "8"
        assert len(result.results) == 1
        assert result.results[0].operator_name == "Telkomsel"

    def test_get_session(self, db_session):
        service, _, _ = self._make_service(db_session)

        session = service.session_repo.create(band="8")
        result = service.get_session(session.id)

        assert result is not None
        assert result.id == session.id

    def test_get_session_not_found(self, db_session):
        service, _, _ = self._make_service(db_session)

        result = service.get_session(9999)

        assert result is None


class TestHistoryService:
    def _make_service(self, db_session):
        return HistoryService(db=db_session)

    def test_get_sessions_empty(self, db_session):
        service = self._make_service(db_session)
        result = service.get_sessions()

        assert result.total == 0
        assert len(result.items) == 0

    def test_get_sessions_with_data(self, db_session):
        service = self._make_service(db_session)

        session = service.session_repo.create(band="8")
        service.result_repo.create(session_id=session.id, operator_name="Telkomsel")

        result = service.get_sessions()

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].operator_name == "Telkomsel"
        assert result.items[0].scan_session_id == session.id

    def test_get_sessions_pagination(self, db_session):
        service = self._make_service(db_session)

        for i in range(15):
            session = service.session_repo.create(band=str([4, 5, 8][i % 3]))
            service.result_repo.create(session_id=session.id, operator_name=f"Op{i}")

        result = service.get_sessions(page=1, page_size=10)

        assert result.total == 15
        assert len(result.items) == 10
        assert result.total_pages == 2

    def test_get_session_detail(self, db_session):
        service = self._make_service(db_session)

        session = service.session_repo.create(band="8")
        scan_result = service.result_repo.create(
            session_id=session.id,
            operator_name="Telkomsel",
        )

        result = service.get_session(scan_result.id)

        assert result is not None
        assert result.operator_name == "Telkomsel"
        assert result.scan_session_id == session.id

    def test_delete_session(self, db_session):
        service = self._make_service(db_session)

        session = service.session_repo.create(band="8")
        scan_result = service.result_repo.create(session_id=session.id)
        deleted = service.delete_session(scan_result.id)

        assert deleted is True

    def test_delete_session_not_found(self, db_session):
        service = self._make_service(db_session)

        deleted = service.delete_session(9999)

        assert deleted is False


class TestSettingsService:
    def _make_service(self, db_session):
        return SettingsService(db=db_session)

    def test_get_all_empty(self, db_session):
        service = self._make_service(db_session)
        result = service.get_all()

        assert len(result) == 0

    def test_set_and_get_value(self, db_session):
        service = self._make_service(db_session)

        service.set_value("test_key", "test_value")
        result = service.get_by_key("test_key")

        assert result is not None
        assert result.key == "test_key"
        assert result.value == "test_value"

    def test_update_settings(self, db_session):
        from app.schemas.scan import SettingUpdateRequest

        service = self._make_service(db_session)

        updates = [
            SettingUpdateRequest(key="key1", value="value1"),
            SettingUpdateRequest(key="key2", value="value2"),
        ]

        results = service.update_settings(updates)

        assert len(results) == 2

    def test_get_by_key_not_found(self, db_session):
        service = self._make_service(db_session)

        result = service.get_by_key("nonexistent")

        assert result is None
