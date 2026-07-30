import math
from datetime import datetime
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
                raise ValueError("start_time tidak boleh lebih besar dari end_time")

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
