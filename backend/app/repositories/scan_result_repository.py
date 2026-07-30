from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc
from typing import Optional
from app.db.models.scan_result import ScanResult
from app.db.models.scan_session import ScanSession


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

        total = query.count()

        if sort.startswith("-"):
            query = query.order_by(desc(ScanSession.scan_time))
        else:
            query = query.order_by(asc(ScanSession.scan_time))

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
