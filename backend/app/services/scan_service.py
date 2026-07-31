import logging
from sqlalchemy.orm import Session
from app.cli import CLIAdapter
from app.gps import GPSProvider
from app.repositories import ScanSessionRepository, ScanResultRepository
from app.schemas.scan import ScanSessionResponse, ScanResultResponse

logger = logging.getLogger(__name__)


class ScanService:
    def __init__(
        self,
        db: Session,
        cli_adapter: CLIAdapter,
        gps_provider: GPSProvider,
    ):
        self.db = db
        self.cli_adapter = cli_adapter
        self.gps_provider = gps_provider
        self.session_repo = ScanSessionRepository(db)
        self.result_repo = ScanResultRepository(db)

    def execute_scan(
        self,
        port: str,
        timeout: int = 30,
        *,
        mission_location_id: int | None = None,
    ) -> ScanSessionResponse:
        logger.info(f"Starting scan on port: {port}")

        location = self.gps_provider.get_location()
        logger.info(f"GPS location: {location.latitude}, {location.longitude}")

        cli_response = self.cli_adapter.execute(port=port, timeout=timeout)
        logger.info(f"CLI returned {len(cli_response.results)} results")

        session = self.session_repo.create(
            tty_port=port,
            latitude=location.latitude,
            longitude=location.longitude,
            mission_location_id=mission_location_id,
        )

        results_data = [
            {
                "operator_name": r.operator_name,
                "mcc": r.mcc,
                "mnc": r.mnc,
                "rat": r.rat,
                "status": r.status,
            }
            for r in cli_response.results
        ]

        self.result_repo.create_bulk(
            session_id=session.id,
            results=results_data,
        )

        logger.info(f"Scan completed, session ID: {session.id}")

        return self._to_response(session)

    def get_session(self, session_id: int) -> ScanSessionResponse | None:
        session = self.session_repo.get_by_id(session_id)
        if not session:
            return None
        return self._to_response(session)

    def _to_response(self, session) -> ScanSessionResponse:
        results = self.result_repo.get_by_session_id(session.id)
        return ScanSessionResponse(
            id=session.id,
            scan_time=session.scan_time,
            tty_port=session.tty_port,
            latitude=session.latitude,
            longitude=session.longitude,
            mission_location_id=session.mission_location_id,
            created_at=session.created_at,
            results=[
                ScanResultResponse(
                    id=r.id,
                    operator_name=r.operator_name,
                    mcc=r.mcc,
                    mnc=r.mnc,
                    rat=r.rat,
                    status=r.status,
                )
                for r in results
            ],
        )
