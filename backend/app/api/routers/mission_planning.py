from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services import MissionPlannerService
from app.schemas.route import ReorderRequest, RouteResponse, SkipRequest, SkipResponse

router = APIRouter(prefix="/api/v1/missions", tags=["missions"])


@router.post("/{mission_id}/plan", response_model=RouteResponse)
def plan_mission(
    mission_id: int,
    db: Session = Depends(get_db),
):
    return MissionPlannerService(db).plan(mission_id)


@router.get("/{mission_id}/route", response_model=RouteResponse)
def get_route(
    mission_id: int,
    db: Session = Depends(get_db),
):
    return MissionPlannerService(db).build_route(mission_id)


@router.post("/{mission_id}/route/reorder", response_model=RouteResponse)
def reorder_route(
    mission_id: int,
    payload: ReorderRequest,
    db: Session = Depends(get_db),
):
    return MissionPlannerService(db).reorder(mission_id, payload)


@router.post("/{mission_id}/route/skip", response_model=SkipResponse)
def skip_route_location(
    mission_id: int,
    payload: SkipRequest,
    db: Session = Depends(get_db),
):
    return MissionPlannerService(db).skip(mission_id, payload.location_id)
