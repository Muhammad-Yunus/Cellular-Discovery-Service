from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket_manager import manager
from app.config.settings import get_settings
from app.gps import create_gps_provider
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

GPS_CHANNEL = "gps"

# Module-level singleton cache to prevent provider recreation on each WS connect
_cached_provider = None
_last_provider_type = None


@router.websocket("/ws/gps")
async def gps_websocket(websocket: WebSocket):
    await manager.connect(websocket, GPS_CHANNEL)

    global _cached_provider, _last_provider_type
    settings = get_settings()
    provider_type = settings.GPS_PROVIDER
    if provider_type != _last_provider_type or _cached_provider is None:
        _cached_provider = create_gps_provider(provider_type=provider_type)
        _last_provider_type = provider_type
    gps_provider = _cached_provider

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
                        "provider": provider_type,
                    },
                },
            )

            await asyncio.sleep(3)
    except WebSocketDisconnect:
        manager.disconnect(websocket, GPS_CHANNEL)
    except Exception as e:
        logger.error(f"GPS WebSocket error: {e}")
        manager.disconnect(websocket, GPS_CHANNEL)
