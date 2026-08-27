from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.config.settings import get_settings
from app.repositories import MissionRepository, MissionLocationRepository
from app.schemas.mission import (
    MissionCreate,
    MissionDetailResponse,
    MissionListResponse,
    MissionResponse,
    MissionStatus,
    MissionUpdate,
)
from app.schemas.mission_location import MissionLocationResponse

ACTIVE_STATUSES = {"STARTING", "RUNNING", "PAUSED"}


class MissionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = MissionRepository(db)
        self.location_repo = MissionLocationRepository(db)

    @staticmethod
    def _ensure_inactive(mission, action: str = "update") -> None:
        if mission.status in ACTIVE_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot {action} mission while it is {mission.status}",
            )

    @staticmethod
    def _ensure_deletable(mission) -> None:
        allowed_statuses = {"IDLE", "STOPPED", "FAILED"}
        if mission.status not in allowed_statuses:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete mission while it is {mission.status}. Only IDLE, STOPPED, or FAILED missions can be deleted.",
            )

    def _ensure_location_belongs(self, mission_id: int, location_id: int) -> None:
        if not self.location_repo.get_by_id(mission_id, location_id):
            raise HTTPException(
                status_code=422,
                detail="start_location_id does not belong to this mission",
            )

    @staticmethod
    def _to_response(mission) -> MissionResponse:
        progress = (
            round(mission.visited_locations / mission.total_locations * 100, 1)
            if mission.total_locations > 0
            else 0.0
        )
        return MissionResponse(
            id=mission.id,
            name=mission.name,
            description=mission.description,
            status=mission.status,
            radius_meters=mission.radius_meters,
            start_location_id=mission.start_location_id,
            current_location_id=mission.current_location_id,
            total_locations=mission.total_locations,
            visited_locations=mission.visited_locations,
            progress_percent=progress,
            started_at=mission.started_at,
            completed_at=mission.completed_at,
            stopped_at=mission.stopped_at,
            created_at=mission.created_at,
            updated_at=mission.updated_at,
        )

    def create(self, payload: MissionCreate) -> MissionResponse:
        settings = get_settings()
        mission = self.repo.create(
            name=payload.name.strip(),
            description=payload.description,
            radius_meters=payload.radius_meters or settings.MISSION_DEFAULT_RADIUS_METERS,
        )
        return self._to_response(mission)

    def list(
        self,
        page: int,
        page_size: int,
        status: str | None = None,
        search: str | None = None,
        sort: str = "-created_at",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> MissionListResponse:
        if status is not None:
            valid_statuses = {s.value for s in MissionStatus}
            if status not in valid_statuses:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid mission status: {status}",
                )

        if start_time and end_time:
            if start_time.timestamp() > end_time.timestamp():
                raise HTTPException(
                    status_code=422,
                    detail="start_time cannot be greater than end_time",
                )

        missions, total = self.repo.list(
            page, page_size, status, search, sort,
            start_time=start_time,
            end_time=end_time,
        )

        return MissionListResponse(
            items=[self._to_response(m) for m in missions],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_detail(self, mission_id: int) -> MissionDetailResponse | None:
        mission = self.repo.get_by_id(mission_id)
        if not mission:
            return None

        base = self._to_response(mission).model_dump()
        return MissionDetailResponse(
            **base,
            locations=[
                MissionLocationResponse.model_validate(loc) for loc in mission.locations
            ],
        )

    def update(self, mission_id: int, payload: MissionUpdate) -> MissionResponse:
        mission = self.repo.get_by_id(mission_id)
        if not mission:
            raise HTTPException(status_code=404, detail="Mission not found")

        self._ensure_inactive(mission, action="update")

        if (
            "start_location_id" in payload.model_fields_set
            and payload.start_location_id is not None
        ):
            self._ensure_location_belongs(mission_id, payload.start_location_id)

        fields = payload.model_dump(exclude_unset=True)
        structural = {"radius_meters", "start_location_id"} & payload.model_fields_set
        mission = self.repo.update(mission, fields)

        if structural:
            self.location_repo.clear_sequence_order(mission_id)

        return self._to_response(mission)

    def delete(self, mission_id: int) -> bool:
        mission = self.repo.get_by_id(mission_id)
        if not mission:
            raise HTTPException(status_code=404, detail="Mission not found")

        self._ensure_deletable(mission)
        return self.repo.delete(mission)
