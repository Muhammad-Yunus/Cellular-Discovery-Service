import math
from datetime import datetime, timedelta
from io import StringIO
import csv
from typing import Optional

from sqlalchemy.orm import Session
from app.repositories import ScanResultRepository
from app.db.models.mission_location import MissionLocation
from app.db.models.scan_session import ScanSession
from app.db.models.scan_result import ScanResult
from app.schemas.scan import ScanResultFlatResponse, PaginatedResponse


class MissionScanService:
    def __init__(self, db: Session):
        self.db = db
        self.result_repo = ScanResultRepository(db)

    def mission_exists(self, mission_id: int) -> bool:
        from app.db.models.mission import Mission
        return self.db.query(Mission).filter(Mission.id == mission_id).first() is not None

    @staticmethod
    def _validate_rat(rat: Optional[str]) -> Optional[str]:
        if rat is None:
            return None
        rat_stripped = rat.strip()
        if rat_stripped and rat_stripped.upper() not in {"GSM", "LTE", "UMTS", "ALL"}:
            raise ValueError("Only GSM, LTE, UMTS, or ALL is allowed for the rat parameter")
        if rat_stripped.upper() == "ALL":
            return None
        return rat_stripped.upper()

    @staticmethod
    def _validate_time_range(
        start_time: Optional[datetime], end_time: Optional[datetime]
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        if start_time and end_time:
            if start_time.timestamp() > end_time.timestamp():
                raise ValueError("start_time cannot be greater than end_time")
        return start_time, end_time

    def get_mission_scans(
        self,
        mission_id: int,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        sort: str = "-scan_time",
        rat: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> PaginatedResponse:
        if not self.mission_exists(mission_id):
            raise ValueError("Mission not found")

        # Validation mirrors HistoryService
        start_time, end_time = self._validate_time_range(start_time, end_time)
        rat_clean = self._validate_rat(rat)

        results, total = self.result_repo.get_mission_flat(
            mission_id=mission_id,
            page=page,
            page_size=page_size,
            search=search,
            sort=sort,
            rat=rat_clean,
            start_time=start_time,
            end_time=end_time,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        items = []
        for r in results:
            session = r.session
            mission_loc_id = session.mission_location_id if session else None
            tower_id = (
                session.mission_location.cellular_tower_id
                if session and session.mission_location
                else None
            )
            tower_name = (
                session.mission_location.cellular_tower_name
                if session and session.mission_location
                else None
            )
            items.append(
                ScanResultFlatResponse(
                    id=r.id,
                    scan_session_id=session.id,
                    scan_time=session.scan_time,
                    band=session.band,
                    latitude=session.latitude,
                    longitude=session.longitude,
                    mission_location_id=mission_loc_id,
                    cellular_tower_id=tower_id,
                    cellular_tower_name=tower_name,
                    created_at=session.created_at,
                    operator_name=r.operator_name,
                    mcc=r.mcc,
                    mnc=r.mnc,
                    rat=r.rat,
                    status=r.status,
                )
            )

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_mission_csv(
        self,
        mission_id: int,
        search: Optional[str] = None,
        sort: str = "-scan_time",
        rat: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> str:
        if not self.mission_exists(mission_id):
            raise ValueError("Mission not found")

        start_time, end_time = self._validate_time_range(start_time, end_time)
        rat_clean = self._validate_rat(rat)

        results, _ = self.result_repo.get_mission_flat(
            mission_id=mission_id,
            page=1,
            page_size=999999,
            search=search,
            sort=sort,
            rat=rat_clean,
            start_time=start_time,
            end_time=end_time,
        )

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "scan_time", "latitude", "longitude",
            "operator_name", "mcc", "mnc", "rat",
            "cellular_tower_id", "cellular_tower_name",
        ])

        for r in results:
            session = r.session
            mission_loc = session.mission_location if session else None
            writer.writerow([
                session.scan_time.isoformat() if session.scan_time else "",
                session.latitude if session else "",
                session.longitude if session else "",
                r.operator_name or "",
                r.mcc or "",
                r.mnc or "",
                r.rat or "",
                mission_loc.cellular_tower_id if mission_loc else "",
                mission_loc.cellular_tower_name if mission_loc else "",
            ])

        return output.getvalue()
