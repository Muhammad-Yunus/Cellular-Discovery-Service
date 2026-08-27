from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import Optional
from datetime import datetime
from app.db.models.mission import Mission


# Map of sortable fields → SQLAlchemy column expression.
# Accepted query params: created_at, name, description
# Prefix "-" means DESC; otherwise ASC. Unknown fields fall back to created_at DESC.
_SORTABLE_FIELDS = {
    "created_at": Mission.created_at,
    "name": Mission.name,
    "description": Mission.description,
}


def _resolve_sort(sort: str):
    """Resolve a `?sort=field` or `?sort=-field` value into a list of
    SQLAlchemy ``order_by`` clauses.
    """
    if not sort:
        sort = "-created_at"

    desc_flag = sort.startswith("-")
    field = sort[1:] if desc_flag else sort

    column = _SORTABLE_FIELDS.get(field)
    if column is None:
        # Unknown field — fall back to created_at descending (stable, default).
        column = Mission.created_at
        desc_flag = True

    direction = desc if desc_flag else asc
    return [direction(column)]


class MissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        description: Optional[str] = None,
        radius_meters: Optional[int] = None,
        band: Optional[str] = None,
    ) -> Mission:
        mission = Mission(
            name=name,
            description=description,
            radius_meters=radius_meters,
            band=band,
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
        sort: str = "-created_at",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> tuple[list[Mission], int]:
        query = self.db.query(Mission)

        if status is not None:
            query = query.filter(Mission.status == status)

        if search:
            query = query.filter(Mission.name.ilike(f"%{search}%"))

        if start_time:
            query = query.filter(Mission.created_at >= start_time)

        if end_time:
            query = query.filter(Mission.created_at <= end_time)

        total = query.count()
        missions = (
            query.order_by(*_resolve_sort(sort))
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
        return (
            self.db.query(Mission)
            .filter(Mission.status.in_(("STARTING", "RUNNING", "PAUSED")))
            .count()
        )

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
