from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DeviceLocationResponse(BaseModel):
    """
    Device location endpoint response.
    
    Mendapatkan lokasi GPS terkini device tanpa bergantung pada mission apapun.
    Endpoint ini independen dan dapat dipanggil kapan saja.
    """
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
    course_deg: Optional[float] = None
    """
    Arah heading dalam derajat (0-360) dari utara sejati.
    None jika tidak tersedia dari GPS.
    """
    speed: float
    """
    Kecepatan device dalam m/s.
    Dihitung dari perubahan posisi antar pembacaan GPS.
    0.0 = device diam (IDLE)
    >0.5 = device bergerak (MOVING)
    """
    status: str
    """
    Status device berdasarkan kecepatan:
    - "MOVING": speed > 0.5 m/s
    - "IDLE": speed <= 0.5 m/s
    - "UNKNOWN": GPS belum tersedia atau error
    """
    datetime: datetime
    """Timestamp lokasi dibaca (UTC+7)"""
    provider: str
    """Nama GPS provider yang aktif (cli, mock, moving_mock, serial)"""
