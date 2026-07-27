from sqlalchemy.orm import Session
from typing import Optional
from app.db.models.scan_result import ScanResult


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
