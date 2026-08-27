from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.cli import CLIScanResponse, CLIScanResult
from app.db.database import get_db
from app.db.models import Mission, MissionLocation, ScanSession
from app.gps import GPSLocation
from app.repositories import ScanSessionRepository
from app.schemas.scan import ScanSessionResponse
from app.services import ScanService
from app.api.dependencies.providers import get_cli_adapter, get_gps_provider


def make_location(db: Session) -> MissionLocation:
    mission = Mission(name="Scan Link Mission")
    db.add(mission)
    db.commit()
    db.refresh(mission)
    loc = MissionLocation(
        mission_id=mission.id,
        cellular_tower_id="LINK-001",
        latitude=-6.2,
        longitude=106.84,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


class TestScanSessionRepository:
    def test_u01_create_without_mission_location_id(self, db_session):
        session = ScanSessionRepository(db_session).create(band="8")

        assert session.mission_location_id is None

    def test_u02_create_with_mission_location_id(self, db_session):
        loc = make_location(db_session)

        session = ScanSessionRepository(db_session).create(
            band="8",
            latitude=-6.2,
            longitude=106.84,
            mission_location_id=loc.id,
        )

        assert session.mission_location_id == loc.id
        db_session.expire_all()
        stored = db_session.query(ScanSession).filter_by(id=session.id).one()
        assert stored.mission_location_id == loc.id


class TestScanServiceLink:
    def _make_service(self, db_session):
        cli_adapter = MagicMock()
        gps_provider = MagicMock()
        return (
            ScanService(
                db=db_session,
                cli_adapter=cli_adapter,
                gps_provider=gps_provider,
            ),
            cli_adapter,
            gps_provider,
        )

    def _mock_deps(self, cli_adapter, gps_provider):
        gps_provider.get_location.return_value = GPSLocation(
            latitude=-6.150676643667096,
            longitude=106.89665223346297,
        )
        cli_adapter.execute.return_value = CLIScanResponse(
            results=[CLIScanResult(operator_name="Telkomsel", mcc="510", mnc="10", rat="LTE", status="Available")],
            raw_output='{"cells": []}',
        )

    def test_u03_execute_scan_without_kwarg(self, db_session):
        service, cli_adapter, gps_provider = self._make_service(db_session)
        self._mock_deps(cli_adapter, gps_provider)

        result = service.execute_scan(band=8)

        assert result.mission_location_id is None
        gps_provider.get_location.assert_called_once()
        cli_adapter.execute.assert_called_once_with(band=8, timeout=30)

    def test_u04_execute_scan_with_mission_location_id(self, db_session):
        service, cli_adapter, gps_provider = self._make_service(db_session)
        self._mock_deps(cli_adapter, gps_provider)
        loc = make_location(db_session)

        result = service.execute_scan(
            band=8, mission_location_id=loc.id
        )

        assert result.mission_location_id == loc.id
        db_session.expire_all()
        stored = db_session.query(ScanSession).filter_by(id=result.id).one()
        assert stored.mission_location_id == loc.id

    def test_u05_scan_session_response_model(self):
        response = ScanSessionResponse(
            id=1,
            scan_time="2026-07-31T09:00:00Z",
            band="8",
            created_at="2026-07-31T09:00:00Z",
        )

        assert response.mission_location_id is None

        with_id = ScanSessionResponse(
            id=2,
            scan_time="2026-07-31T09:00:00Z",
            band="8",
            created_at="2026-07-31T09:00:00Z",
            mission_location_id=7,
        )

        assert with_id.mission_location_id == 7


class TestScanLinkEndpoints:
    def test_e01_scan_returns_null_link(self, client):
        mock_gps = MagicMock()
        mock_gps.get_location.return_value = GPSLocation(
            latitude=-6.150676643667096,
            longitude=106.89665223346297,
        )
        mock_cli = MagicMock()
        mock_cli.execute.return_value = CLIScanResponse(
            results=[CLIScanResult(operator_name="Telkomsel", mcc="510", mnc="10", rat="LTE", status="Available")],
            raw_output='{"cells": []}',
        )

        client.app.dependency_overrides[get_gps_provider] = lambda: mock_gps
        client.app.dependency_overrides[get_cli_adapter] = lambda: mock_cli

        try:
            response = client.post("/api/v1/scan", json={"band": 8})

            assert response.status_code == 200
            assert response.json()["mission_location_id"] is None
        finally:
            client.app.dependency_overrides.pop(get_gps_provider, None)
            client.app.dependency_overrides.pop(get_cli_adapter, None)

    def test_e02_service_scan_stores_link(self, db_session):
        loc = make_location(db_session)
        cli_adapter = MagicMock()
        gps_provider = MagicMock()
        gps_provider.get_location.return_value = GPSLocation(
            latitude=-6.15, longitude=106.89
        )
        cli_adapter.execute.return_value = CLIScanResponse(
            results=[], raw_output='{"cells": []}'
        )
        service = ScanService(db=db_session, cli_adapter=cli_adapter, gps_provider=gps_provider)

        result = service.execute_scan(
            band=8, mission_location_id=loc.id
        )

        assert db_session.query(ScanSession).filter_by(id=result.id).one().mission_location_id == loc.id
