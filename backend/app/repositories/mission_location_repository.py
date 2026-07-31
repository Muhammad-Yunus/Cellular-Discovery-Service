from sqlalchemy.orm import Session
from sqlalchemy import asc, or_
from typing import Optional
from datetime import datetime, timezone
from app.db.models.mission_location import MissionLocation


class MissionLocationRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_batch(self, mission_id: int, rows: list[dict], batch_id: str) -> tuple[int, int]:
        existing = {
            loc.cellular_tower_id: loc
            for loc in self.db.query(MissionLocation)
            .filter(MissionLocation.mission_id == mission_id)
            .all()
        }

        inserted = 0
        updated = 0
        now = datetime.now(timezone.utc)
        processed: dict[str, MissionLocation] = {}

        for row in rows:
            tower_id = row["cellular_tower_id"]
            loc = processed.get(tower_id) or existing.get(tower_id)

            if loc is None:
                loc = MissionLocation(
                    mission_id=mission_id,
                    cellular_tower_id=tower_id,
                    cellular_tower_name=row.get("cellular_tower_name"),
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    upload_batch_id=batch_id,
                )
                self.db.add(loc)
                processed[tower_id] = loc
                inserted += 1
            else:
                loc.cellular_tower_name = row.get("cellular_tower_name")
                loc.latitude = row["latitude"]
                loc.longitude = row["longitude"]
                loc.upload_batch_id = batch_id
                loc.updated_at = now
                processed[tower_id] = loc
                updated += 1

        self.db.commit()
        return inserted, updated

    def list_by_mission(
        self,
        mission_id: int,
        page: int,
        page_size: int,
        search: Optional[str] = None,
    ) -> tuple[list[MissionLocation], int]:
        query = self.db.query(MissionLocation).filter(MissionLocation.mission_id == mission_id)

        if search:
            query = query.filter(
                or_(
                    MissionLocation.cellular_tower_id.ilike(f"%{search}%"),
                    MissionLocation.cellular_tower_name.ilike(f"%{search}%"),
                )
            )

        total = query.count()
        locations = (
            query.order_by(asc(MissionLocation.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return locations, total

    def get_by_id(self, mission_id: int, location_id: int) -> Optional[MissionLocation]:
        return (
            self.db.query(MissionLocation)
            .filter(
                MissionLocation.mission_id == mission_id,
                MissionLocation.id == location_id,
            )
            .first()
        )

    def delete_by_id(self, mission_id: int, location_id: int) -> bool:
        loc = self.get_by_id(mission_id, location_id)
        if not loc:
            return False
        self.db.delete(loc)
        self.db.commit()
        return True

    def bulk_delete_by_batch(self, mission_id: int, upload_batch_id: str) -> int:
        rows = (
            self.db.query(MissionLocation)
            .filter(
                MissionLocation.mission_id == mission_id,
                MissionLocation.upload_batch_id == upload_batch_id,
            )
            .all()
        )
        for row in rows:
            self.db.delete(row)
        self.db.commit()
        return len(rows)

    def count_by_mission(self, mission_id: int) -> int:
        return (
            self.db.query(MissionLocation)
            .filter(MissionLocation.mission_id == mission_id)
            .count()
        )

    def get_all_by_mission(self, mission_id: int) -> list[MissionLocation]:
        return (
            self.db.query(MissionLocation)
            .filter(MissionLocation.mission_id == mission_id)
            .order_by(asc(MissionLocation.id))
            .all()
        )

    def get_by_mission_and_id(
        self, mission_id: int, location_id: int
    ) -> Optional[MissionLocation]:
        return (
            self.db.query(MissionLocation)
            .filter(
                MissionLocation.mission_id == mission_id,
                MissionLocation.id == location_id,
            )
            .first()
        )

    def update_sequence_batch(self, mission_id: int, ordered_ids: list[int]) -> None:
        reset_fields = {
            MissionLocation.status: "PENDING",
            MissionLocation.scan_session_id: None,
            MissionLocation.actual_visit_time: None,
            MissionLocation.visited_at: None,
            MissionLocation.distance_from_previous_meters: None,
            MissionLocation.bearing_from_previous_degrees: None,
            MissionLocation.estimated_arrival_time: None,
        }
        self.db.query(MissionLocation).filter(
            MissionLocation.mission_id == mission_id,
            MissionLocation.status != "VISITED",
        ).update(reset_fields, synchronize_session=False)

        for idx, location_id in enumerate(ordered_ids, start=1):
            self.db.query(MissionLocation).filter(
                MissionLocation.mission_id == mission_id,
                MissionLocation.id == location_id,
            ).update({"sequence_order": idx}, synchronize_session=False)

        self.db.commit()

    def mark_skipped(self, mission_id: int, location_id: int) -> Optional[MissionLocation]:
        loc = self.get_by_mission_and_id(mission_id, location_id)
        if not loc:
            return None
        loc.status = "SKIPPED"
        loc.sequence_order = None
        loc.distance_from_previous_meters = None
        loc.bearing_from_previous_degrees = None
        loc.estimated_arrival_time = None
        loc.actual_visit_time = None
        loc.visited_at = None
        loc.scan_session_id = None
        self.db.commit()
        return loc

    def get_next_pending(self, mission_id: int) -> Optional[MissionLocation]:
        return (
            self.db.query(MissionLocation)
            .filter(
                MissionLocation.mission_id == mission_id,
                MissionLocation.status == "PENDING",
                MissionLocation.sequence_order.isnot(None),
            )
            .order_by(MissionLocation.sequence_order)
            .first()
        )

    def mark_visited(
        self, mission_id: int, location_id: int, scan_session_id: int
    ) -> Optional[MissionLocation]:
        loc = self.get_by_mission_and_id(mission_id, location_id)
        if not loc:
            return None
        now = datetime.now(timezone.utc)
        loc.status = "VISITED"
        loc.scan_session_id = scan_session_id
        loc.actual_visit_time = now
        loc.visited_at = now
        self.db.commit()
        return loc

    def has_planned_locations(self, mission_id: int) -> bool:
        return (
            self.db.query(MissionLocation)
            .filter(
                MissionLocation.mission_id == mission_id,
                MissionLocation.sequence_order.isnot(None),
            )
            .count()
            > 0
        )

    def clear_sequence_order(self, mission_id: int) -> None:
        self.db.query(MissionLocation).filter(
            MissionLocation.mission_id == mission_id
        ).update({"sequence_order": None}, synchronize_session=False)
        self.db.commit()
