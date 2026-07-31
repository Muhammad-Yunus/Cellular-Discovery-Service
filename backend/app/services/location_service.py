import csv
import uuid
from io import StringIO
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.config.settings import get_settings
from app.db.models import Mission
from app.repositories import MissionLocationRepository
from app.schemas.mission_location import (
    BulkDeleteResponse,
    DeleteLocationResponse,
    LocationListResponse,
    UploadLocationResponse,
    UploadRowError,
)


class LocationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = MissionLocationRepository(db)

    @staticmethod
    def parse_csv(raw: bytes) -> list[dict]:
        text = raw.decode("utf-8")
        if not text.strip():
            return []

        reader = csv.DictReader(StringIO(text))

        if reader.fieldnames is None or not {
            "cellular_tower_id",
            "latitude",
            "longitude",
        }.issubset(reader.fieldnames):
            raise ValueError(
                "Invalid CSV header, expected cellular_tower_id,cellular_tower_name,latitude,longitude"
            )

        rows = []
        for idx, record in enumerate(reader, start=2):
            errors: list[str] = []
            tower_id = (record.get("cellular_tower_id") or "").strip()
            tower_name = (record.get("cellular_tower_name") or "").strip()

            latitude = None
            lat_raw = (record.get("latitude") or "").strip()
            if lat_raw == "":
                errors.append("Latitude is required")
            else:
                try:
                    latitude = float(lat_raw)
                    if latitude < -90 or latitude > 90:
                        errors.append(f"Latitude out of range: {lat_raw}")
                        latitude = None
                except ValueError:
                    errors.append(f"Invalid latitude: {lat_raw}")

            longitude = None
            lon_raw = (record.get("longitude") or "").strip()
            if lon_raw == "":
                errors.append("Longitude is required")
            else:
                try:
                    longitude = float(lon_raw)
                    if longitude < -180 or longitude > 180:
                        errors.append(f"Longitude out of range: {lon_raw}")
                        longitude = None
                except ValueError:
                    errors.append(f"Invalid longitude: {lon_raw}")

            if not tower_id:
                errors.append("cellular_tower_id is required")

            rows.append(
                {
                    "row_number": idx,
                    "cellular_tower_id": tower_id,
                    "cellular_tower_name": tower_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "errors": errors,
                }
            )

        return rows

    @staticmethod
    def _ensure_mutable(mission: Mission) -> None:
        if mission.status in ("STARTING", "RUNNING", "PAUSED"):
            raise HTTPException(
                status_code=409,
                detail="Cannot modify locations while mission is running",
            )

    def _get_mission(self, mission_id: int) -> Mission:
        mission = self.db.query(Mission).filter(Mission.id == mission_id).first()
        if not mission:
            raise HTTPException(status_code=404, detail="Mission not found")
        return mission

    def _sync_total(self, mission: Mission) -> None:
        mission.total_locations = self.repo.count_by_mission(mission.id)
        self.db.commit()

    def upload(self, mission_id: int, file_content: bytes) -> UploadLocationResponse:
        mission = self._get_mission(mission_id)
        self._ensure_mutable(mission)

        try:
            rows = self.parse_csv(file_content)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        valid_rows = [row for row in rows if not row["errors"]]
        total_rows = len(rows)

        settings = get_settings()
        if total_rows > settings.MISSION_MAX_LOCATIONS:
            raise HTTPException(
                status_code=422,
                detail=f"CSV file exceeds maximum of {settings.MISSION_MAX_LOCATIONS} rows",
            )

        if not valid_rows:
            raise HTTPException(
                status_code=422,
                detail="CSV file is empty or has no valid rows",
            )

        batch_id = uuid.uuid4().hex
        inserted, updated = self.repo.upsert_batch(mission.id, valid_rows, batch_id)
        self._sync_total(mission)

        errors = [
            UploadRowError(row=row["row_number"], error=error)
            for row in rows
            for error in row["errors"]
        ]

        return UploadLocationResponse(
            upload_batch_id=batch_id,
            mission_id=mission.id,
            total_rows=total_rows,
            inserted=inserted,
            updated=updated,
            skipped=len(rows) - len(valid_rows),
            errors=errors,
        )

    def list_locations(
        self,
        mission_id: int,
        page: int,
        page_size: int,
        search: str | None = None,
    ) -> LocationListResponse:
        self._get_mission(mission_id)
        locations, total = self.repo.list_by_mission(mission_id, page, page_size, search)

        return LocationListResponse(
            items=locations,
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_location(self, mission_id: int, location_id: int):
        self._get_mission(mission_id)
        loc = self.repo.get_by_id(mission_id, location_id)
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")
        return loc

    def delete_location(self, mission_id: int, location_id: int) -> DeleteLocationResponse:
        mission = self._get_mission(mission_id)
        self._ensure_mutable(mission)

        loc = self.repo.get_by_id(mission_id, location_id)
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")

        self.repo.delete_by_id(mission_id, location_id)
        self._sync_total(mission)

        return DeleteLocationResponse(
            message="Location deleted successfully",
            id=location_id,
        )

    def bulk_delete(self, mission_id: int, upload_batch_id: str) -> BulkDeleteResponse:
        if not upload_batch_id or not upload_batch_id.strip():
            raise HTTPException(status_code=422, detail="upload_batch_id is required")

        mission = self._get_mission(mission_id)
        self._ensure_mutable(mission)

        deleted = self.repo.bulk_delete_by_batch(mission_id, upload_batch_id)
        self._sync_total(mission)

        return BulkDeleteResponse(
            message=f"Deleted {deleted} locations from batch {upload_batch_id}",
            deleted=deleted,
        )
