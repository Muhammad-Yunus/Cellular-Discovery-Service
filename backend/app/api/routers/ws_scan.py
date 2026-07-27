from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket_manager import manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

SCAN_CHANNEL = "scan"


@router.websocket("/ws/scan")
async def scan_websocket(websocket: WebSocket):
    await manager.connect(websocket, SCAN_CHANNEL)

    try:
        while True:
            if manager.get_connections_count(SCAN_CHANNEL) == 0:
                break

            data = await websocket.receive_text()
            logger.info(f"Received on scan channel: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, SCAN_CHANNEL)
    except Exception as e:
        logger.error(f"Scan WebSocket error: {e}")
        manager.disconnect(websocket, SCAN_CHANNEL)


async def broadcast_scan_result(result: dict):
    await manager.broadcast(
        SCAN_CHANNEL,
        {
            "type": "scan_result",
            "data": result,
        },
    )
