from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class SDRStatus(BaseModel):
    type: Optional[str] = Field(None, description="RTL-SDR dongle type")
    status: Optional[str] = Field(None, description="active/missing/error/unknown")
    message: Optional[str] = Field(None, description="Detailed status message")

    class Config:
        from_attributes = True


class GPSStatus(BaseModel):
    type: Optional[str] = Field(None, description="GPS module type")
    status: Optional[str] = Field(None, description="active/missing/error/unknown")
    message: Optional[str] = Field(None, description="Detailed status message")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    satellites: Optional[int] = None

    class Config:
        from_attributes = True


class MachineMetrics(BaseModel):
    cpu_percent: Optional[float] = None
    memory_total_mb: Optional[int] = None
    memory_used_mb: Optional[int] = None
    memory_percent: Optional[float] = None
    temperature_c: Optional[float] = None
    disk_total_gb: Optional[float] = None
    disk_used_gb: Optional[float] = None
    disk_percent: Optional[float] = None
    load_avg_1m: Optional[float] = None
    uptime_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class NetworkStatus(BaseModel):
    status: Optional[str] = Field(None, description="online/offline")
    mode: Optional[str] = Field(None, description="dhcp/static/ap")
    ip_address: Optional[str] = None
    gateway: Optional[str] = None
    dns: Optional[List[str]] = Field(default_factory=list)
    hostname: Optional[str] = Field(None, description="Current device hostname")

    class Config:
        from_attributes = True


class HealthSummary(BaseModel):
    total: int
    active: int
    missing: int
    error: int

    class Config:
        from_attributes = True


class DeviceStatusResponse(BaseModel):
    sdr: SDRStatus
    gps: GPSStatus
    machine: MachineMetrics
    network: NetworkStatus
    metadata: dict = Field(
        default_factory=lambda: {
            "collected_at": None,
            "collector_version": "0.3.0",
            "health_summary": None,
        }
    )

    class Config:
        from_attributes = True
