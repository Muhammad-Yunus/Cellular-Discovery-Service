from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket_manager import manager
from app.config.settings import get_settings
from app.gps import create_gps_provider
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

GPS_CHANNEL = "gps"


@router.websocket("/ws/gps")
async def gps_websocket(websocket: WebSocket):
    await manager.connect(websocket, GPS_CHANNEL)

    settings = get_settings()
    gps_provider = create_gps_provider(provider_type=settings.GPS_PROVIDER)

    try:
        while True:
            if manager.get_connections_count(GPS_CHANNEL) == 0:
                break

            location = gps_provider.get_location()

            await manager.broadcast(
                GPS_CHANNEL,
                {
                    "type": "gps_update",
                    "data": {
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                    },
                },
            )

            await asyncio.sleep(10)
    except WebSocketDisconnect:
        manager.disconnect(websocket, GPS_CHANNEL)
    except Exception as e:
        logger.error(f"GPS WebSocket error: {e}")
        manager.disconnect(websocket, GPS_CHANNEL)
