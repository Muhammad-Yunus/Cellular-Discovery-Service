from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc
from typing import Optional
from datetime import datetime
from app.db.models.scan_result import ScanResult
from app.db.models.scan_session import ScanSession
from app.db.models.mission_location import MissionLocation


# Map of sortable fields → SQLAlchemy column expression.
# Accepted query params:
#   - field names documented in API:
#       scan_time, operator_name, mcc, mnc, rat
#   - short aliases used by the frontend/curl:
#       operator (→ operator_name)
# Prefix "-" means DESC; otherwise ASC. Unknown fields fall back to scan_time DESC.
_SORTABLE_FIELDS = {
    "scan_time": ScanSession.scan_time,
    "operator_name": ScanResult.operator_name,
    "operator": ScanResult.operator_name,   # alias used by FE/curl tests
    "mcc": ScanResult.mcc,
    "mnc": ScanResult.mnc,
    "rat": ScanResult.rat,
}


def _resolve_sort(sort: str):
    """Resolve a `?sort=field` or `?sort=-field` value into a list of
    SQLAlchemy ``order_by`` clauses.

    The previous behavior (always order by ``scan_time``) was wrong for any
    field other than ``scan_time`` and made pagination over an unstable order
    silently drop/duplicate rows when scan_time ties occurred.

    Always tie-breaks on ``scan_session.id`` and ``scan_result.id`` so the
    order is deterministic even when the chosen sort column has many ties.
    """
    if not sort:
        sort = "-scan_time"

    desc_flag = sort.startswith("-")
    field = sort[1:] if desc_flag else sort

    column = _SORTABLE_FIELDS.get(field)
    if column is None:
        # Unknown field — fall back to scan_time descending (stable, default).
        column = ScanSession.scan_time
        desc_flag = True

    direction = desc if desc_flag else asc
    return [
        direction(column),
        desc(ScanSession.id),
        desc(ScanResult.id),
    ]


class ScanResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        session_id: int,
        operator_name: Optional[str] = None,
        mcc: Optional[str] = None,
        mnc: Optional[str] = None,
        rat: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ScanResult:
        result = ScanResult(
            session_id=session_id,
            operator_name=operator_name,
            mcc=mcc,
            mnc=mnc,
            rat=rat,
            status=status,
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def create_bulk(
        self,
        session_id: int,
        results: list[dict],
    ) -> list[ScanResult]:
        scan_results = []
        for item in results:
            result = ScanResult(
                session_id=session_id,
                operator_name=item.get("operator_name"),
                mcc=item.get("mcc"),
                mnc=item.get("mnc"),
                rat=item.get("rat"),
                status=item.get("status"),
            )
            self.db.add(result)
            scan_results.append(result)

        self.db.commit()

        for result in scan_results:
            self.db.refresh(result)

        return scan_results

    def get_by_id(self, result_id: int) -> Optional[ScanResult]:
        return self.db.query(ScanResult).filter(ScanResult.id == result_id).first()

    def get_by_session_id(self, session_id: int) -> list[ScanResult]:
        return self.db.query(ScanResult).filter(ScanResult.session_id == session_id).all()

    def get_all_flat(
        self,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        sort: str = "-scan_time",
        rat: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> tuple[list[ScanResult], int]:
        query = self.db.query(ScanResult).join(ScanResult.session)

        if search:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    ScanSession.tty_port.ilike(f"%{search}%"),
                    ScanResult.operator_name.ilike(f"%{search}%"),
                    ScanResult.mcc.ilike(f"%{search}%"),
                    ScanResult.mnc.ilike(f"%{search}%"),
                )
            )

        if rat:
            query = query.filter(ScanResult.rat.ilike(rat))

        if start_time:
            query = query.filter(ScanSession.scan_time >= start_time)

        if end_time:
            query = query.filter(ScanSession.scan_time <= end_time)

        total = query.count()

        # FIX: pass the list of clauses to a single order_by() call.
        # Calling query.order_by(clause) in a loop replaces the previous
        # order_by instead of appending to it, so only the last clause
        # (desc(id)) would have been applied.
        query = query.order_by(*_resolve_sort(sort))

        offset = (page - 1) * page_size
        results = query.offset(offset).limit(page_size).all()

        return results, total

    def get_mission_flat(
        self,
        mission_id: int,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        sort: str = "-scan_time",
        rat: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> tuple[list[ScanResult], int]:
        """Return scan results whose session is linked to a mission location."""
        query = (
            self.db.query(ScanResult)
            .join(ScanResult.session)
            .join(ScanSession.mission_location)
            .filter(MissionLocation.mission_id == mission_id)
        )

        if search:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    ScanSession.tty_port.ilike(f"%{search}%"),
                    ScanResult.operator_name.ilike(f"%{search}%"),
                    ScanResult.mcc.ilike(f"%{search}%"),
                    ScanResult.mnc.ilike(f"%{search}%"),
                )
            )

        if rat:
            query = query.filter(ScanResult.rat.ilike(rat))

        if start_time:
            query = query.filter(ScanSession.scan_time >= start_time)

        if end_time:
            query = query.filter(ScanSession.scan_time <= end_time)

        total = query.count()

        # FIX: pass the list of clauses to a single order_by() call.
        query = query.order_by(*_resolve_sort(sort))

        offset = (page - 1) * page_size
        results = query.offset(offset).limit(page_size).all()

        return results, total

    def get_by_id_with_session(self, result_id: int) -> Optional[ScanResult]:
        return (
            self.db.query(ScanResult)
            .options(joinedload(ScanResult.session))
            .filter(ScanResult.id == result_id)
            .first()
        )

    def delete(self, result_id: int) -> bool:
        result = self.db.query(ScanResult).filter(ScanResult.id == result_id).first()
        if not result:
            return False
        self.db.delete(result)
        self.db.commit()
        return True
