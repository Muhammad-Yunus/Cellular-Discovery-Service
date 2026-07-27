import math
from sqlalchemy.orm import Session
from app.repositories import ScanSessionRepository, ScanResultRepository
from app.schemas.scan import (
    ScanSessionListResponse,
    ScanSessionResponse,
    ScanResultResponse,
    PaginatedResponse,
)


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
    ) -> PaginatedResponse:
        sessions, total = self.session_repo.get_all(
            page=page,
            page_size=page_size,
            search=search,
            sort=sort,
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        items = [
            ScanSessionListResponse(
                id=s.id,
                scan_time=s.scan_time,
                tty_port=s.tty_port,
                latitude=s.latitude,
                longitude=s.longitude,
                created_at=s.created_at,
            )
            for s in sessions
        ]

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_session(self, session_id: int) -> ScanSessionResponse | None:
        session = self.session_repo.get_by_id(session_id)
        if not session:
            return None

        results = self.result_repo.get_by_session_id(session.id)

        return ScanSessionResponse(
            id=session.id,
            scan_time=session.scan_time,
            tty_port=session.tty_port,
            latitude=session.latitude,
            longitude=session.longitude,
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

    def delete_session(self, session_id: int) -> bool:
        return self.session_repo.delete(session_id)
