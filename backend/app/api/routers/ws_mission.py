from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

MISSION_CHANNEL = "mission"


@router.websocket("/ws/mission")
async def mission_websocket(websocket: WebSocket):
    await manager.connect(websocket, MISSION_CHANNEL)
    try:
        while True:
            if manager.get_connections_count(MISSION_CHANNEL) == 0:
                break
            data = await websocket.receive_text()
            logger.info(f"Received on mission channel: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, MISSION_CHANNEL)
    except Exception as e:
        logger.error(f"Mission WebSocket error: {e}")
        manager.disconnect(websocket, MISSION_CHANNEL)


async def broadcast_mission_event(event_type: str, mission_id: int, **data) -> None:
    await manager.broadcast(
        MISSION_CHANNEL,
        {
            "type": event_type,
            "mission_id": mission_id,
            "data": data,
        },
    )
