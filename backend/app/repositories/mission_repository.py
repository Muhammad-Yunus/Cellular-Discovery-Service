from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import Optional
from app.db.models.mission import Mission


class MissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        description: Optional[str] = None,
        radius_meters: Optional[int] = None,
        tty_port: Optional[str] = None,
    ) -> Mission:
        mission = Mission(
            name=name,
            description=description,
            radius_meters=radius_meters,
            tty_port=tty_port,
            status="IDLE",
            total_locations=0,
            visited_locations=0,
        )
        self.db.add(mission)
        self.db.commit()
        self.db.refresh(mission)
        return mission

    def get_by_id(self, mission_id: int) -> Optional[Mission]:
        return self.db.query(Mission).filter(Mission.id == mission_id).first()

    def list(
        self,
        page: int,
        page_size: int,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[Mission], int]:
        query = self.db.query(Mission)

        if status is not None:
            query = query.filter(Mission.status == status)

        if search:
            query = query.filter(Mission.name.ilike(f"%{search}%"))

        total = query.count()
        missions = (
            query.order_by(desc(Mission.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return missions, total

    def update(self, mission: Mission, fields: dict) -> Mission:
        for key, value in fields.items():
            setattr(mission, key, value)
        self.db.commit()
        self.db.refresh(mission)
        return mission

    def get_running_count(self) -> int:
        return self.db.query(Mission).filter(Mission.status == "RUNNING").count()

    def set_status(self, mission_id: int, status: str) -> Optional[Mission]:
        mission = self.get_by_id(mission_id)
        if not mission:
            return None
        mission.status = status
        self.db.commit()
        return mission

    def delete(self, mission: Mission) -> bool:
        self.db.delete(mission)
        self.db.commit()
        return True
