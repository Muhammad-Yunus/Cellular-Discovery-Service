from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func
from typing import Optional
from app.db.models.scan_session import ScanSession


class ScanSessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        band: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        mission_location_id: Optional[int] = None,
    ) -> ScanSession:
        session = ScanSession(
            band=band,
            latitude=latitude,
            longitude=longitude,
            mission_location_id=mission_location_id,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_by_id(self, session_id: int) -> Optional[ScanSession]:
        return self.db.query(ScanSession).filter(ScanSession.id == session_id).first()

    def get_all(
        self,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        sort: str = "-scan_time",
    ) -> tuple[list[ScanSession], int]:
        query = self.db.query(ScanSession)

        if search:
            query = query.filter(
                ScanSession.band.ilike(f"%{search}%")
            )

        total = query.count()

        if sort.startswith("-"):
            query = query.order_by(desc(ScanSession.scan_time))
        else:
            query = query.order_by(asc(ScanSession.scan_time))

        offset = (page - 1) * page_size
        sessions = query.offset(offset).limit(page_size).all()

        return sessions, total

    def delete(self, session_id: int) -> bool:
        session = self.get_by_id(session_id)
        if not session:
            return False
        self.db.delete(session)
        self.db.commit()
        return True

    def get_latest_with_gps(self) -> Optional[ScanSession]:
        """Return the most recent scan session that has a non-null GPS fix.

        Returns ``None`` if no scan has yet recorded latitude/longitude — for
        example on a freshly-flashed device before the operator has run
        ``/api/v1/scan`` at least once. Used by the mission planner to find a
        starting position for the nearest-neighbour route.
        """
        return (
            self.db.query(ScanSession)
            .filter(
                ScanSession.latitude.isnot(None),
                ScanSession.longitude.isnot(None),
            )
            .order_by(desc(ScanSession.scan_time))
            .first()
        )
