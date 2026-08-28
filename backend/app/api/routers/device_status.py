"""
Device Status Router

GET /api/v1/device/status - Returns the latest device peripheral status
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models.device_status import DeviceStatus
from app.schemas.device_status import (
    DeviceStatusResponse,
    SDRStatus,
    GPSStatus,
    MachineMetrics,
    NetworkStatus,
    HealthSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/device", tags=["device"])


@router.get(
    "/status",
    response_model=DeviceStatusResponse,
    summary="Get Device Status",
    description="Returns the latest device peripheral status (SDR, GPS, Machine, Network)."
)
def get_device_status(db: Session = Depends(get_db)):
    """
    Get latest device status from database.

    Data is collected every 5 minutes by background scheduler.
    Returns the most recent record.
    """
    latest = (
        db.query(DeviceStatus)
        .order_by(DeviceStatus.collected_at.desc())
        .first()
    )

    if not latest:
        raise HTTPException(
            status_code=404,
            detail="No device status data available. Scheduler may not be running.",
        )

    # Parse DNS servers from JSON string
    dns_list = []
    if latest.dns_servers:
        try:
            dns_list = json.loads(latest.dns_servers)
        except (json.JSONDecodeError, TypeError):
            dns_list = []

    return DeviceStatusResponse(
        sdr=SDRStatus(
            type=latest.sdr_type,
            status=latest.sdr_status,
            message=latest.sdr_message,
        ),
        gps=GPSStatus(
            type=latest.gps_type,
            status=latest.gps_status,
            message=latest.gps_message,
            latitude=latest.gps_latitude,
            longitude=latest.gps_longitude,
            satellites=latest.gps_satellites,
        ),
        machine=MachineMetrics(
            cpu_percent=latest.cpu_percent,
            memory_total_mb=latest.memory_total_mb,
            memory_used_mb=latest.memory_used_mb,
            memory_percent=latest.memory_percent,
            temperature_c=latest.temperature_c,
            disk_total_gb=latest.disk_total_gb,
            disk_used_gb=latest.disk_used_gb,
            disk_percent=latest.disk_percent,
            load_avg_1m=latest.load_avg_1m,
            uptime_seconds=latest.uptime_seconds,
        ),
        network=NetworkStatus(
            status=latest.network_status,
            mode=latest.network_mode,
            ip_address=latest.ip_address,
            gateway=latest.gateway,
            dns=dns_list,
        ),
        metadata={
            "collected_at": latest.collected_at.isoformat() if latest.collected_at else None,
            "collector_version": latest.collector_version or "0.3.0",
            "health_summary": HealthSummary(
                total=latest.health_summary_total or 0,
                active=latest.health_summary_active or 0,
                missing=latest.health_summary_missing or 0,
                error=latest.health_summary_error or 0,
            ).model_dump(),
        },
    )
