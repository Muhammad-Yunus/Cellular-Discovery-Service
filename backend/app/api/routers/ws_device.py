"""
Device Location WebSocket Endpoint

WebSocket ini menyediakan real-time streaming lokasi GPS device
dengan format response yang sama persis dengan GET /api/v1/device/location.

Keunggulan dibanding polling:
- Tidak ada latency request-response cycle
- Update hanya saat ada perubahan lokasi
- Lebih ringan: 1 koneksi tetap, bukan request tiap 5 detik
- Auto-reconnect jika disconnect
"""

import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket_manager import manager
from app.config.settings import get_settings
from app.gps.factory import create_gps_provider
from app.gps.exceptions import GPSReadError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

DEVICE_CHANNEL = "device_location"
POLL_INTERVAL = 5  # detik


@router.websocket("/ws/device/location")
async def device_location_websocket(websocket: WebSocket):
    """
    WebSocket endpoint untuk streaming lokasi device secara real-time.
    
    Response format sama persis dengan GET /api/v1/device/location:
    {
        "latitude": float,
        "longitude": float,
        "altitude": float | None,
        "accuracy": float | None,
        "speed": float,
        "status": str,
        "datetime": datetime,
        "provider": str
    }
    """
    await manager.connect(websocket, DEVICE_CHANNEL)
    
    settings = get_settings()
    provider_type = settings.GPS_PROVIDER
    provider = create_gps_provider(provider_type)
    
    # State tracking seperti GET endpoint
    _last_location = None
    _last_timestamp = None
    
    try:
        logger.info(f"WebSocket device location connected, provider={provider_type}")
        
        while True:
            # Check if there are still listeners
            if manager.get_connections_count(DEVICE_CHANNEL) == 0:
                break
            
            # Read GPS location
            try:
                location = provider.get_location()
            except GPSReadError as e:
                logger.warning(f"GPS read error: {e}")
                # Still send error status
                await manager.broadcast(
                    DEVICE_CHANNEL,
                    {
                        "type": "device_location",
                        "data": {
                            "latitude": 0.0,
                            "longitude": 0.0,
                            "altitude": None,
                            "accuracy": None,
                            "course_deg": None,
                            "speed": 0.0,
                            "status": "UNKNOWN",
                            "datetime": datetime.now().isoformat(),
                            "provider": provider_type,
                            "error": str(e),
                        }
                    }
                )
                await asyncio.sleep(POLL_INTERVAL)
                continue
            
            # Calculate speed (same logic as GET endpoint)
            speed = 0.0
            if _last_location is not None and _last_timestamp is not None:
                now = datetime.now()
                time_diff = (now - _last_timestamp).total_seconds()
                
                if time_diff > 0:
                    import math
                    R = 6371000.0  # Earth radius in meters
                    lat1, lon1 = math.radians(_last_location.latitude), math.radians(_last_location.longitude)
                    lat2, lon2 = math.radians(location.latitude), math.radians(location.longitude)
                    
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    
                    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                    distance = 2 * R * math.asin(math.sqrt(a))
                    
                    speed = max(0.0, distance / time_diff)
            
            # Determine status
            status = "MOVING" if speed > 0.5 else "IDLE"
            
            # Prepare response (same structure as GET endpoint)
            # Use isoformat() for datetime to ensure JSON serialization
            response_data = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "altitude": location.altitude,
                "accuracy": location.accuracy,
                "course_deg": location.course_deg,
                "speed": round(speed, 2),
                "status": status,
                "datetime": datetime.now().isoformat(),
                "provider": provider_type,
            }
            
            # Broadcast to all connected clients
            try:
                await manager.broadcast(
                    DEVICE_CHANNEL,
                    {
                        "type": "device_location",
                        "data": response_data,
                    }
                )
                logger.info(f"Broadcasted location: lat={location.latitude:.6f}, lon={location.longitude:.6f}, speed={speed:.2f}")
            except Exception as broadcast_err:
                logger.error(f"Broadcast failed: {broadcast_err}")
            
            # Update state
            _last_location = location
            _last_timestamp = datetime.now()
            
            # Log every 10th update to avoid spam
            logger.debug(f"Device location: lat={location.latitude:.6f}, "
                        f"lon={location.longitude:.6f}, "
                        f"speed={speed:.2f} m/s, "
                        f"status={status}")
            
            await asyncio.sleep(POLL_INTERVAL)
            
    except WebSocketDisconnect:
        logger.info("WebSocket device location disconnected")
    except Exception as e:
        logger.error(f"WebSocket device location error: {e}")
    finally:
        try:
            manager.disconnect(websocket, DEVICE_CHANNEL)
        except ValueError:
            pass  # Already disconnected
