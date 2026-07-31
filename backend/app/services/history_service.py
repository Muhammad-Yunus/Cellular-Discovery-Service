import math
from datetime import datetime
from io import StringIO
import csv
from sqlalchemy.orm import Session
from app.repositories import ScanSessionRepository, ScanResultRepository
from app.schemas.scan import ScanResultFlatResponse, PaginatedResponse


class HistoryService:
    def __init__(self, db: Session):
        self.db = db
        self.session_repo = ScanSessionRepository(db)
        self.result_repo = ScanResultRepository(db)

    def get_sessions(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        sort: str = "-scan_time",
        rat: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> PaginatedResponse:
        # Validasi rentang waktu di service layer (untuk keamanan tambahan)
        if start_time and end_time:
            if start_time.timestamp() > end_time.timestamp():
                raise ValueError("start_time cannot be greater than end_time")

        # Validasi filter RAT — hanya GSM, LTE, UMTS, atau ALL (case-insensitive)
        if rat is not None:
            rat_stripped = rat.strip()
            if rat_stripped and rat_stripped.upper() not in {"GSM", "LTE", "UMTS", "ALL"}:
                raise ValueError("Only GSM, LTE, UMTS, or ALL is allowed for the rat parameter")
            # Konversi ALL ke None agar repo tidak mem-filter
            if rat_stripped.upper() == "ALL":
                rat = None

        results, total = self.result_repo.get_all_flat(
            page=page,
            page_size=page_size,
            search=search,
            sort=sort,
            rat=rat,
            start_time=start_time,
            end_time=end_time,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        items = [
            ScanResultFlatResponse(
                id=r.id,
                scan_session_id=r.session_id,
                scan_time=r.session.scan_time,
                tty_port=r.session.tty_port,
                latitude=r.session.latitude,
                longitude=r.session.longitude,
                created_at=r.session.created_at,
                operator_name=r.operator_name,
                mcc=r.mcc,
                mnc=r.mnc,
                rat=r.rat,
                status=r.status,
            )
            for r in results
        ]

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_all_csv(
        self,
        search: str | None = None,
        sort: str = "-scan_time",
        rat: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> str:
        """Export all scan results matching filters to CSV format (string)."""
        # Get ALL results without pagination
        results, _ = self.result_repo.get_all_flat(
            page=1,
            page_size=999999,  # Large number to get all
            search=search,
            sort=sort,
            rat=rat,
            start_time=start_time,
            end_time=end_time,
        )

        # Build CSV in memory
        output = StringIO()
        writer = csv.writer(output)
        # Header
        writer.writerow([
            "id", "session_id", "scan_time", "tty_port", "latitude",
            "longitude", "created_at", "operator_name", "mcc", "mnc", "rat", "status"
        ])
        # Rows
        for r in results:
            writer.writerow([
                r.id,
                r.session_id,
                r.session.scan_time.isoformat() if r.session.scan_time else "",
                r.session.tty_port,
                r.session.latitude,
                r.session.longitude,
                r.session.created_at.isoformat() if r.session.created_at else "",
                r.operator_name or "",
                r.mcc or "",
                r.mnc or "",
                r.rat or "",
                r.status or "",
            ])

        return output.getvalue()

    def get_session(self, result_id: int) -> ScanResultFlatResponse | None:
        result = self.result_repo.get_by_id_with_session(result_id)
        if not result:
            return None

        return ScanResultFlatResponse(
            id=result.id,
            scan_session_id=result.session_id,
            scan_time=result.session.scan_time,
            tty_port=result.session.tty_port,
            latitude=result.session.latitude,
            longitude=result.session.longitude,
            created_at=result.session.created_at,
            operator_name=result.operator_name,
            mcc=result.mcc,
            mnc=result.mnc,
            rat=result.rat,
            status=result.status,
        )

    def delete_session(self, result_id: int) -> bool:
        return self.result_repo.delete(result_id)
