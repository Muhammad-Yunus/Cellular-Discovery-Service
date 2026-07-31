from fastapi import APIRouter, Depends
from app.api.dependencies.providers import get_mission_executor
from app.core.mission_executor import MissionExecutor

router = APIRouter(prefix="/api/v1/missions", tags=["missions"])


@router.post("/{mission_id}/start")
async def start_mission(
    mission_id: int,
    executor: MissionExecutor = Depends(get_mission_executor),
):
    return await executor.start(mission_id)


@router.post("/{mission_id}/pause")
async def pause_mission(
    mission_id: int,
    executor: MissionExecutor = Depends(get_mission_executor),
):
    return await executor.pause(mission_id)


@router.post("/{mission_id}/resume")
async def resume_mission(
    mission_id: int,
    executor: MissionExecutor = Depends(get_mission_executor),
):
    return await executor.resume(mission_id)


@router.post("/{mission_id}/stop")
async def stop_mission(
    mission_id: int,
    executor: MissionExecutor = Depends(get_mission_executor),
):
    return await executor.stop(mission_id)


@router.get("/{mission_id}/status")
def mission_status(
    mission_id: int,
    executor: MissionExecutor = Depends(get_mission_executor),
):
    return executor.get_status(mission_id)


@router.get("/{mission_id}/logs")
def mission_logs(
    mission_id: int,
    executor: MissionExecutor = Depends(get_mission_executor),
):
    return executor.get_logs(mission_id)
