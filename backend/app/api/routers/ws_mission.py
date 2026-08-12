from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

MISSION_CHANNEL = "mission"


@router.websocket("/ws/mission")
@router.websocket("/ws/missions")
async def mission_websocket(websocket: WebSocket):
    channel = "mission" if websocket.url.path == "/ws/mission" else "missions_plural"
    # Normalize channel name so both paths share the same connection pool
    await manager.connect(websocket, channel)
    try:
        while True:
            if manager.get_connections_count(channel) == 0:
                break
            data = await websocket.receive_text()
            logger.info(f"Received on {channel} channel: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)
    except Exception as e:
        logger.error(f"Mission WebSocket error: {e}")
        manager.disconnect(websocket, channel)


async def broadcast_mission_event(event_type: str, mission_id: int, **data) -> None:
    await manager.broadcast(
        MISSION_CHANNEL,
        {
            "type": event_type,
            "mission_id": mission_id,
            "data": data,
        },
    )
