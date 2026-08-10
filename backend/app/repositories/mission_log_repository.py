from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models.mission_log import MissionLog


class MissionLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, mission_id: int, timestamp: datetime, event_type: str, message: Optional[str] = None) -> MissionLog:
        log = MissionLog(
            mission_id=mission_id,
            timestamp=timestamp,
            event_type=event_type,
            message=message,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_by_mission_id(self, mission_id: int) -> list[MissionLog]:
        return self.db.query(MissionLog).filter(
            MissionLog.mission_id == mission_id
        ).order_by(MissionLog.timestamp.desc()).all()

    def count_by_mission_id(self, mission_id: int) -> int:
        return self.db.query(MissionLog).filter(
            MissionLog.mission_id == mission_id
        ).count()
