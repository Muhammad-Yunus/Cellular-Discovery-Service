"""
Device Location API Endpoint

Endpoint ini menyediakan informasi lokasi GPS device secara independen,
tanpa bergantung pada mission apapun. Endpoint dapat dipanggil kapan saja
untuk mendapatkan:
- Latitude & Longitude terkini
- Speed (kecepatan) dalam m/s
- Status device (MOVING, IDLE, UNKNOWN)
- Timestamp pembacaan
- GPS provider yang aktif
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from app.config.settings import get_settings
from app.gps.factory import create_gps_provider
from app.gps.schemas import GPSLocation
from app.gps.exceptions import GPSReadError
from app.schemas.device import DeviceLocationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/device", tags=["device"])


# Global cache untuk tracking kecepatan
_last_location: GPSLocation | None = None
_last_timestamp: datetime | None = None
_last_provider_type: str | None = None
_cached_provider = None


def _calculate_speed(
    current: GPSLocation,
    previous: GPSLocation,
    time_diff_seconds: float
) -> float:
    """
    Menghitung kecepatan berdasarkan perubahan posisi dan waktu.
    
    Args:
        current: Lokasi GPS saat ini
        previous: Lokasi GPS sebelumnya
        time_diff_seconds: Selisih waktu dalam detik
    
    Returns:
        Kecepatan dalam m/s
    """
    import math
    
    # Haversine formula untuk menghitung jarak
    R = 6371000.0  # Radius bumi dalam meter
    lat1, lon1 = math.radians(previous.latitude), math.radians(previous.longitude)
    lat2, lon2 = math.radians(current.latitude), math.radians(current.longitude)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    distance = 2 * R * math.asin(math.sqrt(a))
    
    # Hitung kecepatan
    if time_diff_seconds > 0:
        return distance / time_diff_seconds
    return 0.0


def _get_device_status(speed: float) -> str:
    """
    Menentukan status device berdasarkan kecepatan.
    
    Args:
        speed: Kecepatan dalam m/s
    
    Returns:
        "MOVING" jika speed > 0.5 m/s
        "IDLE" jika speed <= 0.5 m/s
    """
    if speed > 0.5:
        return "MOVING"
    return "IDLE"


@router.get(
    "/location",
    response_model=DeviceLocationResponse,
    summary="Get Device Location",
    description="Mendapatkan lokasi GPS terkini device secara independen (tidak terikat mission)."
)
def get_device_location():
    """
    Endpoint untuk mendapatkan lokasi GPS device saat ini.
    
    Endpoint ini:
    - Membaca lokasi GPS dari provider yang aktif (berdasarkan GPS_PROVIDER di .env)
    - Menghitung kecepatan dari perubahan posisi
    - Menentukan status device (MOVING/IDLE/UNKNOWN)
    - Mengembalikan timestamp pembacaan
    
    Response:
        - latitude: Koordinat lintang
        - longitude: Koordinat bujur
        - altitude: Ketinggian (jika tersedia)
        - accuracy: Akurasi GPS (jika tersedia)
        - speed: Kecepatan dalam m/s
        - status: Status device (MOVING/IDLE/UNKNOWN)
        - datetime: Timestamp pembacaan
        - provider: Nama GPS provider yang aktif
    """
    global _last_location, _last_timestamp, _last_provider_type, _cached_provider
    
    try:
        # Ambil konfigurasi dari settings
        settings = get_settings()
        provider_type = settings.GPS_PROVIDER
        
        # Singleton pattern: reuse provider instance untuk moving_mock
        # agar koordinat tetap bergerak (tidak reset ke start)
        if provider_type != _last_provider_type or _cached_provider is None:
            _cached_provider = create_gps_provider(provider_type)
            _last_provider_type = provider_type
        provider = _cached_provider
        
        # Baca lokasi GPS
        location = provider.get_location()
        
        # Hitung kecepatan
        speed = 0.0
        if _last_location is not None and _last_timestamp is not None:
            now = datetime.now()
            time_diff = (now - _last_timestamp).total_seconds()
            
            if time_diff > 0:
                speed = _calculate_speed(location, _last_location, time_diff)
                # Clamp speed ke 0 jika negatif (error)
                speed = max(0.0, speed)
        
        # Update cache
        _last_location = location
        _last_timestamp = datetime.now()
        
        # Tentukan status
        status = _get_device_status(speed)
        
        logger.info(
            f"Device location: lat={location.latitude:.6f}, "
            f"lon={location.longitude:.6f}, "
            f"speed={speed:.2f} m/s, "
            f"status={status}, "
            f"provider={provider_type}"
        )
        
        return DeviceLocationResponse(
            latitude=location.latitude,
            longitude=location.longitude,
            altitude=location.altitude,
            accuracy=location.accuracy,
            course_deg=location.course_deg,
            speed=round(speed, 2),
            status=status,
            datetime=_last_timestamp,
            provider=provider_type,
        )
        
    except GPSReadError as e:
        logger.error(f"GPS read error: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "UNKNOWN",
                "error": str(e),
                "provider": settings.GPS_PROVIDER,
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error getting device location: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get device location: {str(e)}"
        )
